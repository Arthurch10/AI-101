"""微博财经博主追踪工具 - CLI 主入口"""

import json
import os
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from . import database as db
from .scraper import WeiboScraper
from .ranker import BloggerRanker
from .analyzer import OpinionAnalyzer
from .advisor import InvestmentAdvisor
from .report import select_bloggers_interactive, render_deep_report

console = Console()


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """微博财经博主追踪与投资辅助工具 (WFT)"""
    db.init_db()


# ===================================================================
# 博主管理
# ===================================================================

@cli.group("blogger")
def blogger_group():
    """博主管理命令"""
    pass


@blogger_group.command("add")
@click.argument("uid")
@click.option("--manual", is_flag=True, help="标记为手动筛选")
@click.option("--cookie", default="", help="微博 Cookie (提高抓取成功率)")
def add_blogger(uid, manual, cookie):
    """添加博主 (通过微博 UID)"""
    config = load_config()
    cookie = cookie or config.get("weibo_cookie", "")

    console.print(f"正在获取博主 [cyan]{uid}[/] 信息...", style="bold")
    scraper = WeiboScraper(cookie=cookie)
    info = scraper.fetch_blogger_info(uid)

    if not info:
        console.print("[red]获取博主信息失败，请检查 UID 是否正确或是否需要设置 Cookie[/]")
        return

    db.add_blogger(
        uid=info["uid"],
        screen_name=info["screen_name"],
        description=info["description"],
        followers_count=info["followers_count"],
        statuses_count=info["statuses_count"],
        verified=info["verified"],
        verified_reason=info["verified_reason"],
        manual_selected=manual,
    )

    console.print(Panel(
        f"[green]✓[/] 已添加博主: [bold cyan]{info['screen_name']}[/]\n"
        f"  粉丝: {info['followers_count']:,}\n"
        f"  微博数: {info['statuses_count']:,}\n"
        f"  认证: {info.get('verified_reason', '无')}\n"
        f"  手动筛选: {'是' if manual else '否'}",
        title="添加成功",
    ))


@blogger_group.command("search")
@click.argument("keyword")
@click.option("--cookie", default="", help="微博 Cookie")
def search_blogger(keyword, cookie):
    """搜索财经博主"""
    config = load_config()
    cookie = cookie or config.get("weibo_cookie", "")

    console.print(f"搜索 [cyan]{keyword}[/] 相关博主...", style="bold")
    scraper = WeiboScraper(cookie=cookie)
    results = scraper.search_bloggers(keyword)

    if not results:
        console.print("[yellow]未找到相关博主[/]")
        return

    table = Table(title=f"搜索结果: {keyword}")
    table.add_column("UID", style="cyan", width=12)
    table.add_column("昵称", style="bold")
    table.add_column("粉丝数", justify="right")
    table.add_column("认证", style="green")
    table.add_column("简介", max_width=40)

    for b in results[:20]:
        table.add_row(
            b["uid"],
            b["screen_name"],
            f"{b['followers_count']:,}",
            "V" if b["verified"] else "",
            (b["description"][:37] + "...") if len(b.get("description", "")) > 40 else b.get("description", ""),
        )

    console.print(table)
    console.print("\n使用 [bold]wft blogger add <UID>[/] 添加博主")


@blogger_group.command("list")
def list_bloggers():
    """列出所有已添加的博主"""
    bloggers = db.get_all_bloggers()
    if not bloggers:
        console.print("[yellow]尚未添加任何博主[/]")
        console.print("使用 [bold]wft blogger add <UID>[/] 添加博主")
        return

    table = Table(title="已追踪博主列表")
    table.add_column("UID", style="cyan", width=12)
    table.add_column("昵称", style="bold")
    table.add_column("粉丝数", justify="right")
    table.add_column("认证", style="green")
    table.add_column("手动筛选", justify="center")
    table.add_column("帖子数", justify="right")

    for b in bloggers:
        post_count = db.get_blogger_post_count(b["uid"])
        table.add_row(
            b["uid"],
            b["screen_name"],
            f"{b['followers_count']:,}",
            b.get("verified_reason", "") or ("V" if b["verified"] else ""),
            "★" if b["manual_selected"] else "",
            str(post_count),
        )

    console.print(table)


@blogger_group.command("remove")
@click.argument("uid")
def remove_blogger(uid):
    """移除博主"""
    blogger = db.get_blogger(uid)
    if not blogger:
        console.print(f"[red]未找到 UID 为 {uid} 的博主[/]")
        return
    db.remove_blogger(uid)
    console.print(f"[green]✓[/] 已移除博主: [bold]{blogger['screen_name']}[/]")


@blogger_group.command("select")
@click.argument("uid")
def select_blogger(uid):
    """手动标记博主为优选"""
    blogger = db.get_blogger(uid)
    if not blogger:
        console.print(f"[red]未找到 UID 为 {uid} 的博主[/]")
        return
    db.add_blogger(
        uid=blogger["uid"], screen_name=blogger["screen_name"],
        description=blogger.get("description", ""),
        followers_count=blogger.get("followers_count", 0),
        statuses_count=blogger.get("statuses_count", 0),
        verified=blogger.get("verified", False),
        verified_reason=blogger.get("verified_reason", ""),
        manual_selected=True,
    )
    console.print(f"[green]✓[/] 已将 [bold cyan]{blogger['screen_name']}[/] 标记为手动优选")


# ===================================================================
# 数据采集
# ===================================================================

@cli.command("fetch")
@click.option("--uid", default=None, help="指定博主 UID，不指定则抓取所有")
@click.option("--pages", default=3, help="抓取页数 (每页约10条)")
@click.option("--cookie", default="", help="微博 Cookie")
def fetch_posts(uid, pages, cookie):
    """抓取博主微博数据"""
    config = load_config()
    cookie = cookie or config.get("weibo_cookie", "")

    scraper = WeiboScraper(cookie=cookie)

    if uid:
        blogger = db.get_blogger(uid)
        name = blogger["screen_name"] if blogger else uid
        console.print(f"正在抓取 [cyan]{name}[/] 的微博...", style="bold")
        count = scraper.fetch_and_save(uid, pages)
        console.print(f"[green]✓[/] 获取 {count} 条微博")
    else:
        console.print("正在抓取所有博主的微博...", style="bold")
        results = scraper.fetch_all_bloggers_posts(pages)
        total = sum(results.values())
        console.print(f"\n[green]✓[/] 共获取 {total} 条微博 (来自 {len(results)} 位博主)")


# ===================================================================
# 分析命令
# ===================================================================

@cli.command("analyze")
@click.option("--llm", is_flag=True, help="使用 LLM 进行深度分析")
def analyze(llm):
    """分析未处理的博主帖子"""
    config = load_config()
    api_key = config.get("openai_api_key", "")
    base_url = config.get("llm_base_url", "")
    model = config.get("llm_model", "")

    analyzer = OpinionAnalyzer(api_key, base_url, model)

    console.print("正在分析帖子...", style="bold")
    results = analyzer.analyze_unprocessed(use_llm=llm)

    if not results:
        console.print("[yellow]没有待分析的帖子[/]")
        return

    # 统计
    bullish = sum(1 for r in results if r["market_view"] == "bullish")
    bearish = sum(1 for r in results if r["market_view"] == "bearish")
    neutral = sum(1 for r in results if r["market_view"] == "neutral")

    console.print(f"\n[green]✓[/] 已分析 {len(results)} 条帖子")
    console.print(f"  看多: {bullish}  |  看空: {bearish}  |  中性: {neutral}")


@cli.command("summary")
@click.option("--uid", default=None, help="指定博主 UID")
def show_summary(uid):
    """查看博主观点摘要"""
    config = load_config()
    analyzer = OpinionAnalyzer(
        config.get("openai_api_key", ""),
        config.get("llm_base_url", ""),
        config.get("llm_model", ""),
    )

    if uid:
        uids = [uid]
    else:
        bloggers = db.get_all_bloggers()
        uids = [b["uid"] for b in bloggers]

    for u in uids:
        blogger = db.get_blogger(u)
        summary = analyzer.get_blogger_summary(u)
        if not summary:
            continue

        name = blogger["screen_name"] if blogger else u

        table = Table(title=f"博主观点摘要: {name}")
        table.add_column("指标", style="bold")
        table.add_column("数值", justify="right")

        table.add_row("分析帖子数", str(summary["total_opinions"]))
        table.add_row("平均情绪", f"{summary['avg_sentiment']:+.4f}")
        table.add_row("看多占比", f"{summary['bullish_pct']}%")
        table.add_row("看空占比", f"{summary['bearish_pct']}%")
        table.add_row("中性占比", f"{summary['neutral_pct']}%")
        table.add_row("最近观点", summary["recent_view"])
        table.add_row("平均置信度", f"{summary['avg_confidence']:.4f}")

        console.print(table)

        if summary["top_sectors"]:
            sectors = " | ".join(f"{s}({c})" for s, c in summary["top_sectors"][:5])
            console.print(f"  热门板块: {sectors}")
        if summary["top_tickers"]:
            tickers = " | ".join(f"{t}({c})" for t, c in summary["top_tickers"][:5])
            console.print(f"  关注个股: {tickers}")
        console.print()


# ===================================================================
# 排名命令
# ===================================================================

@cli.command("rank")
@click.option("--top", default=10, help="显示前 N 名")
def show_rankings(top):
    """显示博主排名 (TOP-N)"""
    ranker = BloggerRanker()
    rankings = ranker.get_top_n(top)

    if not rankings:
        console.print("[yellow]暂无排名数据，请先添加博主并抓取数据[/]")
        return

    table = Table(title=f"博主排名 TOP {top}")
    table.add_column("#", style="bold", width=4)
    table.add_column("博主", style="cyan")
    table.add_column("综合分", justify="right", style="bold green")
    table.add_column("准确率", justify="right")
    table.add_column("影响力", justify="right")
    table.add_column("活跃度", justify="right")
    table.add_column("一致性", justify="right")

    for i, r in enumerate(rankings, 1):
        blogger = db.get_blogger(r["blogger_uid"])
        name = blogger["screen_name"] if blogger else r["blogger_uid"]
        table.add_row(
            str(i),
            name,
            f"{r['score']:.4f}",
            f"{r['accuracy_score']:.4f}",
            f"{r['influence_score']:.4f}",
            f"{r['activity_score']:.4f}",
            f"{r['consistency_score']:.4f}",
        )

    console.print(table)


@cli.command("top3")
def show_top3():
    """显示优选 TOP3 博主 (手动筛选优先 + 算法补齐)"""
    ranker = BloggerRanker()
    top3 = ranker.get_selected_top3()

    if not top3:
        console.print("[yellow]暂无数据，请先添加博主[/]")
        return

    console.print(Panel("[bold]优选 TOP3 博主[/]", style="bold green"))
    for i, r in enumerate(top3, 1):
        blogger = db.get_blogger(r["blogger_uid"])
        name = blogger["screen_name"] if blogger else r["blogger_uid"]
        is_manual = blogger.get("manual_selected") if blogger else False

        console.print(
            f"  [bold yellow]#{i}[/] [bold cyan]{name}[/]"
            f" {'[手动筛选]' if is_manual else '[算法推荐]'}"
            f"  综合分: [green]{r['score']:.4f}[/]"
        )


# ===================================================================
# 投资建议
# ===================================================================

@cli.command("advice")
@click.option("--days", default=7, help="分析天数范围")
@click.option("--top3-only", is_flag=True, help="仅基于 TOP3 博主生成建议")
def show_advice(days, top3_only):
    """生成投资参考建议"""
    config = load_config()
    advisor = InvestmentAdvisor(
        config.get("openai_api_key", ""),
        config.get("llm_base_url", ""),
        config.get("llm_model", ""),
    )

    blogger_uids = None
    if top3_only:
        ranker = BloggerRanker()
        top3 = ranker.get_selected_top3()
        blogger_uids = [r["blogger_uid"] for r in top3]

    console.print("正在生成投资参考...", style="bold")
    report = advisor.generate_advice(blogger_uids, days)

    if "error" in report:
        console.print(f"[red]{report['error']}[/]")
        return

    console.print(Panel(
        report["advice"],
        title=f"投资参考报告 ({report['generated_at']})",
        border_style="green",
    ))


# ===================================================================
# 深度分析
# ===================================================================

@cli.command("deep")
@click.option("--uid", "uids", multiple=True,
              help="指定博主 UID，可多次传入；不传则交互选择")
@click.option("--all", "select_all", is_flag=True, help="分析全部博主")
@click.option("--llm", is_flag=True, help="使用 LLM 深度分析")
def deep_analysis(uids, select_all, llm):
    """深度情绪分析: 市场走向/板块个股/量化指标 (可交互选择博主)"""
    console.print(Panel.fit(
        "[bold cyan]微博财经博主 · 深度情绪分析系统[/]",
        border_style="cyan",
    ))

    if uids:
        selected_uids = list(uids)
    elif select_all:
        selected_uids = [b["uid"] for b in db.get_all_bloggers()]
    else:
        selected = select_bloggers_interactive()
        selected_uids = [b["uid"] for b in selected]

    if not selected_uids:
        console.print("[yellow]未选择任何博主，请先用 wft blogger add 添加博主[/]")
        return

    render_deep_report(selected_uids, use_llm=llm)


# ===================================================================
# 一键执行
# ===================================================================

@cli.command("run")
@click.option("--pages", default=3, help="抓取页数")
@click.option("--llm", is_flag=True, help="使用 LLM 分析")
@click.option("--cookie", default="", help="微博 Cookie")
def run_pipeline(pages, llm, cookie):
    """一键执行: 抓取 -> 分析 -> 排名 -> 建议"""
    config = load_config()
    cookie = cookie or config.get("weibo_cookie", "")

    # Step 1: 抓取
    console.print("\n[bold]Step 1/4: 抓取微博数据[/]")
    scraper = WeiboScraper(cookie=cookie)
    results = scraper.fetch_all_bloggers_posts(pages)
    total = sum(results.values())
    console.print(f"[green]✓[/] 获取 {total} 条微博\n")

    # Step 2: 分析
    console.print("[bold]Step 2/4: 分析观点[/]")
    analyzer = OpinionAnalyzer(
        config.get("openai_api_key", ""),
        config.get("llm_base_url", ""),
        config.get("llm_model", ""),
    )
    opinions = analyzer.analyze_unprocessed(use_llm=llm)
    console.print(f"[green]✓[/] 分析 {len(opinions)} 条帖子\n")

    # Step 3: 排名
    console.print("[bold]Step 3/4: 博主排名[/]")
    ranker = BloggerRanker()
    top3 = ranker.get_selected_top3()
    for i, r in enumerate(top3, 1):
        blogger = db.get_blogger(r["blogger_uid"])
        name = blogger["screen_name"] if blogger else r["blogger_uid"]
        console.print(f"  #{i} {name} (分数: {r['score']:.4f})")
    console.print()

    # Step 4: 生成建议
    console.print("[bold]Step 4/4: 生成投资建议[/]")
    advisor = InvestmentAdvisor(
        config.get("openai_api_key", ""),
        config.get("llm_base_url", ""),
        config.get("llm_model", ""),
    )
    report = advisor.generate_advice(days=7)
    if "error" not in report:
        console.print(Panel(
            report["advice"],
            title="投资参考报告",
            border_style="green",
        ))
    else:
        console.print(f"[yellow]{report['error']}[/]")


if __name__ == "__main__":
    cli()
