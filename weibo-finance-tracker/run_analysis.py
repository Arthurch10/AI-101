#!/usr/bin/env python3
"""交互式深度分析 - 选择博主，情绪分析，市场走向/板块个股/量化指标"""

import sys

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from src import database as db
from src.demo import load_demo_data
from src.analyzer import OpinionAnalyzer
from src.deep_analysis import DeepAnalyzer

console = Console()


def _bar(value, width=10, max_value=100):
    """生成 ASCII 进度条"""
    filled = int(round(value / max_value * width))
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


def _sent_color(score):
    """情绪分对应颜色"""
    if score >= 0.15:
        return "green"
    if score <= -0.15:
        return "red"
    return "yellow"


def select_bloggers():
    """让用户选择要分析的博主"""
    bloggers = db.get_all_bloggers()

    table = Table(title="📋 可选博主列表")
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("博主", style="bold")
    table.add_column("粉丝数", justify="right")
    table.add_column("认证", style="green")
    table.add_column("手动优选", justify="center")

    for i, b in enumerate(bloggers, 1):
        table.add_row(
            str(i), b["screen_name"], f"{b['followers_count']:,}",
            b.get("verified_reason", ""),
            "★" if b.get("manual_selected") else "",
        )
    console.print(table)

    if not sys.stdin.isatty():
        console.print("[dim]非交互环境，默认分析全部博主[/]")
        return bloggers

    raw = console.input(
        "\n[bold]请输入要分析的博主编号（逗号分隔，或输入 all 全选）:[/] "
    ).strip()

    if raw.lower() in ("all", "", "全部"):
        return bloggers

    selected = []
    for part in raw.replace("，", ",").split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(bloggers):
                selected.append(bloggers[idx])
    return selected or bloggers


def run():
    console.print(Panel.fit(
        "[bold cyan]微博财经博主 · 深度情绪分析系统[/]",
        border_style="cyan",
    ))

    # 加载数据
    console.print("\n[dim]初始化数据...[/]")
    load_demo_data()

    # 选择博主
    selected = select_bloggers()
    uids = [b["uid"] for b in selected]
    names = ", ".join(b["screen_name"] for b in selected)
    console.print(f"\n[green]✓[/] 已选择 {len(selected)} 位博主: [bold]{names}[/]\n")

    # NLP 情绪分析
    console.print("[dim]正在进行 NLP 情绪分析...[/]")
    analyzer = OpinionAnalyzer()
    analyzer.analyze_unprocessed(use_llm=False)

    # 收集选中博主的帖子与观点
    posts, opinions = [], []
    for uid in uids:
        posts.extend(db.get_posts(uid, limit=500))
        opinions.extend(db.get_opinions(uid, limit=500))

    if not opinions:
        console.print("[red]没有可分析的数据[/]")
        return

    deep = DeepAnalyzer()

    # ============ Section 1: 市场整体走向与热度 ============
    trend = deep.analyze_market_trend(opinions, posts)

    dir_color = {"上行": "green", "下行": "red", "震荡": "yellow"}[trend["trend_direction"]]
    mom_sign = "+" if trend["momentum"] >= 0 else ""

    trend_body = (
        f"[bold]市场走向:[/] [{dir_color}]{trend['trend_direction']}[/]   "
        f"[bold]趋势强度:[/] {_bar(trend['trend_strength'])} {trend['trend_strength']}/100\n"
        f"[bold]市场热度:[/] {_bar(trend['heat_index'])} {trend['heat_index']}/100   "
        f"[bold]情绪动量:[/] [{_sent_color(trend['momentum']/100)}]{mom_sign}{trend['momentum']}[/]\n"
        f"[bold]量能信号:[/] {trend['volume_signal']}   "
        f"[bold]平均情绪:[/] [{_sent_color(trend['avg_sentiment'])}]{trend['avg_sentiment']:+.3f}[/]   "
        f"[bold]总帖数:[/] {trend['total_posts']}   "
        f"[bold]总互动:[/] {trend['total_engagement']:,}"
    )
    console.print(Panel(trend_body, title="① 市场整体走向与热度", border_style="cyan"))

    # 周度情绪趋势图
    console.print("[bold]  近 4 周情绪趋势:[/]")
    for label, sent in trend["weekly_sentiment_trend"]:
        norm = int((sent + 1) / 2 * 20)  # -1~1 映射到 0~20
        bar = "█" * max(norm, 0)
        color = _sent_color(sent)
        console.print(f"    {label}  [{color}]{bar:<20}[/] {sent:+.3f}")
    console.print()

    # ============ Section 2: 板块与个股 ============
    sectors = deep.analyze_sectors(opinions, posts)
    tickers = deep.analyze_tickers(opinions, posts)

    sec_table = Table(title="② 板块讨论度 · 共识度 · 情绪")
    sec_table.add_column("板块", style="bold")
    sec_table.add_column("提及", justify="right")
    sec_table.add_column("讨论热度", justify="left")
    sec_table.add_column("共识度", justify="left")
    sec_table.add_column("情绪分", justify="right")
    sec_table.add_column("情绪", style="bold")

    for s in sectors[:12]:
        c = _sent_color(s["sentiment_score"])
        sec_table.add_row(
            s["name"], str(s["mention_count"]),
            f"{_bar(s['discussion_heat'], 8)} {s['discussion_heat']:.0f}",
            f"{_bar(s['consensus_degree'], 8)} {s['consensus_degree']:.0f}",
            f"[{c}]{s['sentiment_score']:+.3f}[/]",
            f"[{c}]{s['sentiment_label']}[/]",
        )
    console.print(sec_table)

    tk_table = Table(title="个股讨论度 · 情绪 · 共识")
    tk_table.add_column("个股", style="bold")
    tk_table.add_column("提及", justify="right")
    tk_table.add_column("情绪分", justify="right")
    tk_table.add_column("博主共识", justify="left")
    tk_table.add_column("情绪", style="bold")

    for t in tickers[:12]:
        c = _sent_color(t["sentiment_score"])
        tk_table.add_row(
            t["name"], str(t["mention_count"]),
            f"[{c}]{t['sentiment_score']:+.3f}[/]",
            f"{_bar(t['blogger_consensus'], 8)} {t['blogger_consensus']:.0f}",
            f"[{c}]{t['sentiment_label']}[/]",
        )
    console.print(tk_table)

    # ============ Section 3: 量化参考指标 ============
    bloggers = [db.get_blogger(u) for u in uids]
    quant = deep.compute_quant_indicators(opinions, posts, bloggers)

    q_table = Table(title="③ 量化参考指标")
    q_table.add_column("指标", style="bold cyan")
    q_table.add_column("数值", justify="right", style="bold")
    q_table.add_column("含义")

    bsi = quant["blogger_sentiment_index"]
    q_table.add_row("博主情绪指数 BSI", f"{bsi:+.1f}",
                    "范围 -100~100，>30 偏乐观，<-30 偏悲观")
    q_table.add_row("市场热度指数 MHI", f"{quant['market_heat_index']:.1f}",
                    "范围 0~100，>60 高关注度")
    q_table.add_row("共识指数 CI", f"{quant['consensus_index']:.1f}",
                    "范围 0~100，越高博主观点越一致")
    sm = quant["sentiment_momentum"]
    q_table.add_row("情绪动量 SM", f"{sm:+.1f}",
                    "正值情绪改善，负值情绪转弱")
    q_table.add_row("风险偏好指数 RAI", f"{quant['risk_appetite_index']:.1f}",
                    "范围 0~100，看多帖占比")
    console.print(q_table)

    # 板块轮动
    rot = quant["sector_rotation_signal"]
    rot_text = ""
    if rot["gaining"]:
        rot_text += f"[green]▲ 升温:[/] {', '.join(rot['gaining'])}   "
    if rot["losing"]:
        rot_text += f"[red]▼ 降温:[/] {', '.join(rot['losing'])}"
    if rot_text:
        console.print(Panel(rot_text, title="板块轮动信号", border_style="magenta"))

    # 信号综述
    console.print(Panel(
        quant["signal_summary"],
        title="📊 量化信号综述", border_style="green",
    ))

    # 风险提示
    console.print(Panel(
        "⚠️ 本报告基于微博财经博主观点的 NLP 语义与情绪分析生成，所有指标"
        "仅供参考，[bold]不构成投资建议[/]。投资有风险，入市需谨慎。",
        border_style="yellow",
    ))


if __name__ == "__main__":
    run()
