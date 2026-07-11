#!/usr/bin/env python3
"""交互式深度分析 - 选择博主，情绪分析，市场走向/板块个股/量化指标

等价于 `wft deep` 命令，保留为独立脚本方便直接运行。
"""

from rich.panel import Panel

from src.demo import load_demo_data
from src.report import console, select_bloggers_interactive, render_deep_report


def run():
    console.print(Panel.fit(
        "[bold cyan]微博财经博主 · 深度情绪分析系统[/]",
        border_style="cyan",
    ))

    console.print("\n[dim]初始化数据...[/]")
    load_demo_data()

    selected = select_bloggers_interactive()
    uids = [b["uid"] for b in selected]
    if not uids:
        console.print("[yellow]未选择任何博主[/]")
        return

    render_deep_report(uids, use_llm=False)


if __name__ == "__main__":
    run()
