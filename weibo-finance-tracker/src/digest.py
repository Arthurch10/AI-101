"""AI 观点流研判 - 把观点流浓缩成一段自然语言研判"""

from collections import Counter


def _avg(nums):
    nums = [n for n in nums if n is not None]
    return sum(nums) / len(nums) if nums else 0.0


def generate_digest(feed_items):
    """
    基于观点流生成研判摘要

    feed_items: [{market_view, sentiment, sectors[], tickers[], screen_name, content}]
    返回: {text, bullish, bearish, neutral, avg_sentiment,
           top_sectors, bull_tickers, bear_tickers, divergence}
    """
    if not feed_items:
        return {"text": "暂无观点数据。", "bullish": 0, "bearish": 0,
                "neutral": 0, "avg_sentiment": 0.0, "top_sectors": [],
                "bull_tickers": [], "bear_tickers": [], "divergence": []}

    views = [f.get("market_view") or "neutral" for f in feed_items]
    bull = views.count("bullish")
    bear = views.count("bearish")
    neu = views.count("neutral")
    total = len(feed_items)
    avg_sent = round(_avg([f.get("sentiment") for f in feed_items]), 3)

    # 板块热度
    sector_freq = Counter()
    # 分方向的板块，用于识别分歧
    sector_bull, sector_bear = Counter(), Counter()
    bull_tickers, bear_tickers = Counter(), Counter()
    for f in feed_items:
        view = f.get("market_view")
        for s in (f.get("sectors") or []):
            sector_freq[s] += 1
            if view == "bullish":
                sector_bull[s] += 1
            elif view == "bearish":
                sector_bear[s] += 1
        for t in (f.get("tickers") or []):
            if view == "bullish":
                bull_tickers[t] += 1
            elif view == "bearish":
                bear_tickers[t] += 1

    top_sectors = [s for s, _ in sector_freq.most_common(3)]
    top_bull = [t for t, _ in bull_tickers.most_common(3)]
    top_bear = [t for t, _ in bear_tickers.most_common(3)]

    # 分歧板块: 既有看多又有看空
    divergence = [s for s in sector_freq
                  if sector_bull.get(s, 0) > 0 and sector_bear.get(s, 0) > 0]

    # 整体倾向
    if bull > bear * 1.5:
        tone = "整体偏多"
    elif bear > bull * 1.5:
        tone = "整体偏空"
    elif bull > 0 and bear > 0:
        tone = "多空分歧"
    else:
        tone = "中性观望"

    # 组装文本
    parts = [f"近期 {total} 条观点中，看多 {bull} 条 / 看空 {bear} 条 / 中性 {neu} 条，{tone}"]
    if top_sectors:
        parts.append(f"主线聚焦 {' / '.join(top_sectors)}")
    if top_bull:
        parts.append(f"看多个股 {' / '.join(top_bull)}")
    if top_bear:
        parts.append(f"看空个股 {' / '.join(top_bear)}")
    if divergence:
        parts.append(f"分歧板块 {' / '.join(divergence[:3])}（多空并存，需谨慎）")
    parts.append(f"平均情绪 {avg_sent:+.3f}")

    text = "；".join(parts) + "。"

    return {
        "text": text,
        "bullish": bull, "bearish": bear, "neutral": neu,
        "avg_sentiment": avg_sent,
        "top_sectors": top_sectors,
        "bull_tickers": top_bull,
        "bear_tickers": top_bear,
        "divergence": divergence[:3],
    }
