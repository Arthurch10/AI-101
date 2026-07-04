#!/usr/bin/env python3
"""导出自包含静态 HTML 报告（独立脚本，等价 `wft export`）

用法:  python3 export_report.py [输出路径]
默认输出:  report.html
"""

import sys

from src.html_report import export


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "report.html"
    path, data = export(out, auto_demo=True)
    print(f"✓ 已生成静态报告: {path}")
    print(f"  分析博主: {', '.join(s['screen_name'] for s in data['selected'])}")
    print(f"  市场走向: {data['trend']['trend_direction']} | 热度: "
          f"{data['trend']['heat_index']} | BSI: {data['quant']['blogger_sentiment_index']}")
    print("  用浏览器直接打开该文件即可查看完整可视化报告。")


if __name__ == "__main__":
    main()
