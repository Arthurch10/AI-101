"""定时任务调度 - 周期性抓取微博、分析观点、更新排名"""

import os
import time
from datetime import datetime

import schedule

from . import database as db
from .scraper import WeiboScraper
from .analyzer import OpinionAnalyzer
from .ranker import BloggerRanker


LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "scheduler.log")


def _log(msg):
    """打印并写入日志文件"""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_job(cookie="", pages=3, use_llm=False):
    """执行一次完整流程: 抓取 → 分析 → 排名"""
    db.init_db()
    bloggers = db.get_all_bloggers()
    if not bloggers:
        _log("跳过: 数据库暂无博主，请先用 wft blogger add 添加")
        return {"fetched": 0, "analyzed": 0, "ranked": 0}

    _log(f"任务开始: {len(bloggers)} 位博主")

    # 1) 抓取
    scraper = WeiboScraper(cookie=cookie)
    fetched = 0
    for b in bloggers:
        try:
            fetched += scraper.fetch_and_save(b["uid"], pages)
        except Exception as e:  # noqa: BLE001
            _log(f"  抓取失败 [{b['screen_name']}]: {e}")
    _log(f"  抓取 {fetched} 条新微博")

    # 2) 分析
    analyzer = OpinionAnalyzer()
    opinions = analyzer.analyze_unprocessed(use_llm=use_llm)
    _log(f"  分析 {len(opinions)} 条帖子")

    # 3) 排名
    ranker = BloggerRanker()
    rankings = ranker.rank_all()
    top3 = ranker.get_selected_top3()
    top_names = ", ".join(
        (db.get_blogger(r["blogger_uid"]) or {}).get("screen_name", r["blogger_uid"])
        for r in top3
    )
    _log(f"  排名更新完成，优选 TOP3: {top_names}")
    _log("任务结束")

    return {"fetched": fetched, "analyzed": len(opinions), "ranked": len(rankings)}


def start(interval_hours=None, at_time=None, cookie="", pages=3, use_llm=False):
    """启动调度循环

    interval_hours: 每 N 小时执行
    at_time: 每天在 "HH:MM" 执行 (与 interval_hours 二选一)
    """
    def job():
        run_job(cookie=cookie, pages=pages, use_llm=use_llm)

    if at_time:
        schedule.every().day.at(at_time).do(job)
        _log(f"已启动定时任务: 每天 {at_time} 执行")
    else:
        hours = interval_hours or 24
        schedule.every(hours).hours.do(job)
        _log(f"已启动定时任务: 每 {hours} 小时执行")

    _log("首次立即执行一次...")
    job()

    _log("进入等待循环 (Ctrl+C 退出)")
    while True:
        schedule.run_pending()
        time.sleep(30)
