#!/usr/bin/env python3
"""微博财经博主追踪 - Web 界面

浏览器中选择博主、运行情绪分析，查看三大结论：
  ① 市场整体走向与热度
  ② 板块与个股讨论度/共识度/情绪
  ③ 量化参考指标

运行:  python3 webapp.py  然后打开 http://127.0.0.1:5000
"""

import os

from flask import Flask, jsonify, request, render_template

from src import database as db
from src.demo import load_demo_data
from src.analyzer import OpinionAnalyzer
from src.ranker import BloggerRanker
from src.deep_analysis import DeepAnalyzer

app = Flask(__name__)


def _ensure_data():
    """确保数据库有数据；无数据时加载演示数据"""
    db.init_db()
    if not db.get_all_bloggers():
        load_demo_data()


@app.route("/")
def index():
    _ensure_data()
    return render_template("index.html")


@app.route("/api/bloggers")
def api_bloggers():
    """返回全部博主列表"""
    _ensure_data()
    bloggers = db.get_all_bloggers()
    return jsonify([
        {
            "uid": b["uid"],
            "screen_name": b["screen_name"],
            "followers_count": b["followers_count"],
            "verified_reason": b.get("verified_reason", ""),
            "manual_selected": bool(b.get("manual_selected")),
            "post_count": db.get_blogger_post_count(b["uid"]),
        }
        for b in bloggers
    ])


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """对选中博主运行深度分析，返回三大结论 JSON"""
    _ensure_data()
    data = request.get_json(silent=True) or {}
    uids = data.get("uids") or [b["uid"] for b in db.get_all_bloggers()]

    # NLP 情绪分析（分析尚未处理的帖子）
    analyzer = OpinionAnalyzer()
    analyzer.analyze_unprocessed(use_llm=False)

    posts, opinions = [], []
    for uid in uids:
        posts.extend(db.get_posts(uid, limit=500))
        opinions.extend(db.get_opinions(uid, limit=500))

    if not opinions:
        return jsonify({"error": "没有可分析的数据"}), 400

    deep = DeepAnalyzer()
    bloggers = [db.get_blogger(u) for u in uids]

    trend = deep.analyze_market_trend(opinions, posts)
    sectors = deep.analyze_sectors(opinions, posts)
    tickers = deep.analyze_tickers(opinions, posts)
    quant = deep.compute_quant_indicators(opinions, posts, bloggers)

    return jsonify({
        "selected": [
            {"uid": u, "screen_name": (db.get_blogger(u) or {}).get("screen_name", u)}
            for u in uids
        ],
        "trend": trend,
        "sectors": sectors[:15],
        "tickers": tickers[:15],
        "quant": quant,
    })


@app.route("/api/ranking")
def api_ranking():
    """返回博主 TOP-N 排名"""
    _ensure_data()
    top_n = int(request.args.get("top", 10))
    ranker = BloggerRanker()
    rankings = ranker.get_top_n(top_n)
    result = []
    for i, r in enumerate(rankings, 1):
        blogger = db.get_blogger(r["blogger_uid"])
        result.append({
            "rank": i,
            "screen_name": blogger["screen_name"] if blogger else r["blogger_uid"],
            "score": r["score"],
            "accuracy_score": r["accuracy_score"],
            "influence_score": r["influence_score"],
            "activity_score": r["activity_score"],
            "consistency_score": r["consistency_score"],
        })
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  微博财经博主追踪 Web 界面")
    print(f"  请在浏览器打开: http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
