#!/usr/bin/env python3
"""微博财经博主追踪 - Web 界面

浏览器中选择博主、运行情绪分析，查看三大结论：
  ① 市场整体走向与热度
  ② 板块与个股讨论度/共识度/情绪
  ③ 量化参考指标

运行:  python3 webapp.py  然后打开 http://127.0.0.1:5000
"""

import json
import os

from flask import Flask, jsonify, request, render_template

from src import database as db
from src.demo import load_demo_data
from src.scraper import WeiboScraper
from src.analyzer import OpinionAnalyzer
from src.ranker import BloggerRanker
from src.deep_analysis import DeepAnalyzer
from src.advisor import InvestmentAdvisor

app = Flask(__name__)


def load_config():
    path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


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
            "uid": r["blogger_uid"],
            "screen_name": blogger["screen_name"] if blogger else r["blogger_uid"],
            "score": r["score"],
            "accuracy_score": r["accuracy_score"],
            "influence_score": r["influence_score"],
            "activity_score": r["activity_score"],
            "consistency_score": r["consistency_score"],
        })
    return jsonify(result)


@app.route("/api/top3")
def api_top3():
    """返回优选 TOP3 博主（手动优先 + 算法补齐）"""
    _ensure_data()
    ranker = BloggerRanker()
    top3 = ranker.get_selected_top3()
    result = []
    for i, r in enumerate(top3, 1):
        blogger = db.get_blogger(r["blogger_uid"])
        result.append({
            "rank": i,
            "uid": r["blogger_uid"],
            "screen_name": blogger["screen_name"] if blogger else r["blogger_uid"],
            "score": r["score"],
            "source": "手动筛选" if (blogger and blogger.get("manual_selected")) else "算法推荐",
        })
    return jsonify(result)


@app.route("/api/advice", methods=["POST"])
def api_advice():
    """生成投资参考建议（聚合博主观点）"""
    _ensure_data()
    data = request.get_json(silent=True) or {}
    uids = data.get("uids") or None
    days = int(data.get("days", 7))
    top3_only = bool(data.get("top3_only"))

    if top3_only:
        ranker = BloggerRanker()
        uids = [r["blogger_uid"] for r in ranker.get_selected_top3()]

    # 确保帖子已完成情绪分析
    OpinionAnalyzer().analyze_unprocessed(use_llm=False)

    cfg = load_config()
    advisor = InvestmentAdvisor(
        cfg.get("openai_api_key", ""),
        cfg.get("llm_base_url", ""),
        cfg.get("llm_model", ""),
    )
    report = advisor.generate_advice(uids, days)
    if "error" in report:
        return jsonify({"error": report["error"]}), 400

    consensus = report["market_consensus"]
    return jsonify({
        "generated_at": report["generated_at"],
        "advice": report["advice"],
        "consensus": {
            "consensus": consensus["consensus"],
            "bullish_pct": consensus["bullish_pct"],
            "bearish_pct": consensus["bearish_pct"],
            "avg_sentiment": consensus["avg_sentiment"],
            "hot_sectors": consensus["hot_sectors"][:6],
            "hot_tickers": consensus["hot_tickers"][:6],
            "total_opinions": consensus["total_opinions"],
        },
    })


@app.route("/api/search_bloggers")
def api_search_bloggers():
    """按昵称搜索博主，返回候选列表"""
    _ensure_data()
    q = request.args.get("q", "").strip()
    cookie = request.args.get("cookie", "") or load_config().get("weibo_cookie", "")
    if not q:
        return jsonify({"error": "请输入昵称关键词"}), 400

    scraper = WeiboScraper(cookie=cookie)
    results = scraper.search_bloggers(q)
    if not results:
        return jsonify({
            "results": [],
            "hint": "未找到匹配博主。微博搜索通常需要登录态，请填写 Cookie 后重试，或改用 UID 添加。",
        })
    exact = [b for b in results if b["screen_name"] == q]
    ordered = exact + [b for b in results if b not in exact]
    return jsonify({"results": [
        {"uid": b["uid"], "screen_name": b["screen_name"],
         "followers_count": b["followers_count"],
         "verified_reason": b.get("verified_reason", ""),
         "description": b.get("description", "")[:60]}
        for b in ordered[:15]
    ]})


@app.route("/api/add_blogger", methods=["POST"])
def api_add_blogger():
    """通过微博 UID 或昵称添加真实博主"""
    _ensure_data()
    data = request.get_json(silent=True) or {}
    query = str(data.get("uid", "") or data.get("query", "")).strip()
    cookie = data.get("cookie", "") or load_config().get("weibo_cookie", "")
    if not query:
        return jsonify({"error": "请提供微博 UID 或昵称"}), 400

    scraper = WeiboScraper(cookie=cookie)

    if query.isdigit():
        info = scraper.fetch_blogger_info(query)
        if not info:
            return jsonify({
                "error": "获取博主信息失败。微博接口通常需要登录态，请填写微博 Cookie 后重试。"
            }), 400
    else:
        results = scraper.search_bloggers(query)
        if not results:
            return jsonify({
                "error": "未找到该昵称的博主。请填写 Cookie 后重试，或改用 UID 添加。"
            }), 400
        exact = [b for b in results if b["screen_name"] == query]
        info = (exact or results)[0]

    db.add_blogger(
        uid=info["uid"], screen_name=info["screen_name"],
        description=info.get("description", ""),
        followers_count=info.get("followers_count", 0),
        statuses_count=info.get("statuses_count", 0),
        verified=info.get("verified", False),
        verified_reason=info.get("verified_reason", ""),
        manual_selected=bool(data.get("manual")),
    )
    return jsonify({"ok": True, "blogger": {
        "uid": info["uid"], "screen_name": info["screen_name"],
        "followers_count": info.get("followers_count", 0),
    }})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """抓取所有博主的最新微博（真实数据）"""
    _ensure_data()
    data = request.get_json(silent=True) or {}
    cookie = data.get("cookie", "") or load_config().get("weibo_cookie", "")
    pages = int(data.get("pages", 3))

    scraper = WeiboScraper(cookie=cookie)
    results, errors = {}, []
    for blogger in db.get_all_bloggers():
        uid = blogger["uid"]
        try:
            count = scraper.fetch_and_save(uid, pages)
            results[blogger["screen_name"]] = count
        except Exception as e:  # noqa: BLE001
            results[blogger["screen_name"]] = 0
            errors.append(f"{blogger['screen_name']}: {e}")

    total = sum(results.values())
    # 抓取到新数据后立即做一次情绪分析
    if total > 0:
        OpinionAnalyzer().analyze_unprocessed(use_llm=False)

    payload = {"ok": True, "total": total, "per_blogger": results}
    if total == 0:
        payload["hint"] = ("未抓取到新数据。微博接口通常需要登录态，"
                           "请填写微博 Cookie 后重试；或确认已添加真实博主 UID。")
    if errors:
        payload["errors"] = errors[:5]
    return jsonify(payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  微博财经博主追踪 Web 界面")
    print(f"  请在浏览器打开: http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
