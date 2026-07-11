"""深度语义分析模块 - 市场走向、板块个股热度、量化参考指标"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np

from .analyzer import BULLISH_WORDS, BEARISH_WORDS


def _sentiment_label(score):
    """情绪分转文字标签"""
    if score >= 0.4:
        return "强烈看多"
    if score >= 0.15:
        return "看多"
    if score > -0.15:
        return "中性"
    if score > -0.4:
        return "看空"
    return "强烈看空"


def _safe_date(s):
    """解析日期字符串，失败返回 None"""
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19] if len(s) >= 19 else s, fmt)
        except ValueError:
            continue
    return None


class DeepAnalyzer:
    """深度语义与量化分析器"""

    # ------------------------------------------------------------------
    # 1. 市场整体走向与热度
    # ------------------------------------------------------------------

    def analyze_market_trend(self, opinions, posts):
        """分析市场整体走向、热度、动量"""
        sentiments = [o["sentiment"] for o in opinions if o.get("sentiment") is not None]
        avg_sent = float(np.mean(sentiments)) if sentiments else 0.0

        # 趋势方向
        if avg_sent >= 0.15:
            trend_direction = "上行"
        elif avg_sent <= -0.15:
            trend_direction = "下行"
        else:
            trend_direction = "震荡"

        # 趋势强度 0-100
        trend_strength = round(min(abs(avg_sent) * 200, 100), 1)

        # 热度指数：互动量 + 发帖量
        total_engagement = sum(
            p.get("reposts_count", 0) + p.get("comments_count", 0) + p.get("attitudes_count", 0)
            for p in posts
        )
        avg_engagement = total_engagement / len(posts) if posts else 0
        # 对数缩放到 0-100
        heat_index = round(min(np.log10(max(avg_engagement, 1)) / 4.5 * 100, 100), 1)

        # 周度情绪趋势（最近 4 周）
        weekly = self._weekly_sentiment(opinions, posts)

        # 动量：最近一周相对前一周的情绪变化
        if len(weekly) >= 2:
            momentum = round((weekly[-1][1] - weekly[-2][1]) * 100, 1)
        else:
            momentum = 0.0

        # 成交量信号：发帖频率趋势
        volume_signal = self._posting_volume_signal(posts)

        return {
            "trend_direction": trend_direction,
            "trend_strength": trend_strength,
            "heat_index": heat_index,
            "momentum": momentum,
            "volume_signal": volume_signal,
            "avg_sentiment": round(avg_sent, 4),
            "total_posts": len(posts),
            "total_engagement": total_engagement,
            "weekly_sentiment_trend": weekly,
        }

    def _weekly_sentiment(self, opinions, posts):
        """计算最近 4 周的周度平均情绪"""
        # 建立 post_id -> sentiment 映射
        sent_map = {o["post_id"]: o["sentiment"] for o in opinions
                    if o.get("sentiment") is not None}

        now = datetime.now()
        buckets = defaultdict(list)
        for p in posts:
            dt = _safe_date(p.get("created_at"))
            if not dt:
                continue
            s = sent_map.get(p["post_id"])
            if s is None:
                continue
            weeks_ago = (now - dt).days // 7
            if weeks_ago <= 3:
                buckets[weeks_ago].append(s)

        result = []
        for w in range(3, -1, -1):  # 3周前 -> 本周
            label = (now - timedelta(weeks=w)).strftime("%m/%d")
            vals = buckets.get(w, [])
            avg = round(float(np.mean(vals)), 4) if vals else 0.0
            result.append((label, avg))
        return result

    def _posting_volume_signal(self, posts):
        """发帖频率趋势信号"""
        now = datetime.now()
        recent_7 = sum(1 for p in posts if (d := _safe_date(p.get("created_at")))
                       and (now - d).days <= 7)
        prev_7 = sum(1 for p in posts if (d := _safe_date(p.get("created_at")))
                     and 7 < (now - d).days <= 14)
        if prev_7 == 0:
            return "放量" if recent_7 > 0 else "平稳"
        ratio = recent_7 / prev_7
        if ratio >= 1.3:
            return "放量"
        if ratio <= 0.7:
            return "缩量"
        return "平稳"

    # ------------------------------------------------------------------
    # 2. 板块分析
    # ------------------------------------------------------------------

    def analyze_sectors(self, opinions, posts):
        """分析各板块讨论度、共识度、情绪"""
        blogger_map = {}  # sector -> set of blogger_uid
        sector_sentiments = defaultdict(list)
        sector_bloggers = defaultdict(list)
        sector_tickers = defaultdict(list)
        sector_count = Counter()

        for o in opinions:
            sectors = [s for s in (o.get("sectors") or "").split(",") if s]
            tickers = [t for t in (o.get("tickers") or "").split(",") if t]
            sent = o.get("sentiment", 0) or 0
            uid = o.get("blogger_uid")
            for sec in sectors:
                sector_count[sec] += 1
                sector_sentiments[sec].append(sent)
                sector_bloggers[sec].append(uid)
                sector_tickers[sec].extend(tickers)

        results = []
        for sec, count in sector_count.most_common():
            sents = sector_sentiments[sec]
            avg_sent = float(np.mean(sents)) if sents else 0.0
            # 共识度：情绪方向一致性 = 1 - 归一化标准差
            std = float(np.std(sents)) if len(sents) > 1 else 0.0
            consensus = round(max(0, (1 - std)) * 100, 1)
            # 讨论热度
            heat = round(min(count / max(sector_count.most_common(1)[0][1], 1) * 100, 100), 1)
            # 参与博主
            blogger_freq = Counter(sector_bloggers[sec])
            top_bloggers = [uid for uid, _ in blogger_freq.most_common(3)]
            # 关联个股
            ticker_freq = Counter(t for t in sector_tickers[sec] if t)
            related = [t for t, _ in ticker_freq.most_common(3)]

            results.append({
                "name": sec,
                "mention_count": count,
                "discussion_heat": heat,
                "consensus_degree": consensus,
                "sentiment_score": round(avg_sent, 4),
                "sentiment_label": _sentiment_label(avg_sent),
                "top_bloggers": top_bloggers,
                "related_tickers": related,
            })
        return results

    # ------------------------------------------------------------------
    # 3. 个股分析
    # ------------------------------------------------------------------

    def analyze_tickers(self, opinions, posts):
        """分析个股讨论度、情绪、博主共识"""
        ticker_sentiments = defaultdict(list)
        ticker_count = Counter()

        for o in opinions:
            tickers = [t for t in (o.get("tickers") or "").split(",") if t]
            sent = o.get("sentiment", 0) or 0
            for t in tickers:
                ticker_count[t] += 1
                ticker_sentiments[t].append(sent)

        results = []
        for t, count in ticker_count.most_common():
            sents = ticker_sentiments[t]
            avg_sent = float(np.mean(sents)) if sents else 0.0
            std = float(np.std(sents)) if len(sents) > 1 else 0.0
            consensus = round(max(0, (1 - std)) * 100, 1)
            results.append({
                "name": t,
                "mention_count": count,
                "sentiment_score": round(avg_sent, 4),
                "blogger_consensus": consensus,
                "sentiment_label": _sentiment_label(avg_sent),
            })
        return results

    # ------------------------------------------------------------------
    # 4. 量化参考指标
    # ------------------------------------------------------------------

    def compute_quant_indicators(self, opinions, posts, bloggers):
        """计算量化参考指标"""
        sentiments = [o["sentiment"] for o in opinions if o.get("sentiment") is not None]

        # 博主情绪指数 BSI: -100 ~ 100（按博主粉丝加权）
        blogger_weight = {b["uid"]: np.log10(max(b.get("followers_count", 1), 1))
                          for b in bloggers}
        weighted_sum, weight_total = 0.0, 0.0
        for o in opinions:
            if o.get("sentiment") is None:
                continue
            w = blogger_weight.get(o.get("blogger_uid"), 1.0)
            weighted_sum += o["sentiment"] * w
            weight_total += w
        bsi = round((weighted_sum / weight_total) * 100, 1) if weight_total else 0.0

        # 市场热度指数 MHI: 0-100
        total_engagement = sum(
            p.get("reposts_count", 0) + p.get("comments_count", 0) + p.get("attitudes_count", 0)
            for p in posts
        )
        avg_engagement = total_engagement / len(posts) if posts else 0
        engagement_score = min(np.log10(max(avg_engagement, 1)) / 4.5 * 100, 100)
        now = datetime.now()
        recent_posts = sum(1 for p in posts if (d := _safe_date(p.get("created_at")))
                           and (now - d).days <= 7)
        freq_score = min(recent_posts / max(len(bloggers), 1) / 5 * 100, 100)
        mhi = round(engagement_score * 0.6 + freq_score * 0.4, 1)

        # 共识指数 CI: 0-100（情绪标准差越小共识越高）
        std = float(np.std(sentiments)) if len(sentiments) > 1 else 0.0
        ci = round(max(0, (1 - std)) * 100, 1)

        # 情绪动量 SM: 最近一周 vs 之前情绪变化
        recent_sents = [o["sentiment"] for o in opinions
                        if o.get("sentiment") is not None]  # 已按时间排序（DESC）
        if len(recent_sents) >= 6:
            half = len(recent_sents) // 2
            sm = round((np.mean(recent_sents[:half]) - np.mean(recent_sents[half:])) * 100, 1)
        else:
            sm = 0.0

        # 风险偏好指数 RAI: 0-100（看多帖占比）
        views = [o.get("market_view") for o in opinions if o.get("market_view")]
        bull = views.count("bullish")
        total_v = len(views) or 1
        rai = round(bull / total_v * 100, 1)

        # 板块轮动信号
        rotation = self._sector_rotation(opinions, posts)

        # 信号综述
        summary = self._signal_summary(bsi, mhi, ci, sm, rai)

        return {
            "blogger_sentiment_index": bsi,
            "market_heat_index": mhi,
            "consensus_index": ci,
            "sentiment_momentum": sm,
            "risk_appetite_index": rai,
            "sector_rotation_signal": rotation,
            "signal_summary": summary,
        }

    def _sector_rotation(self, opinions, posts):
        """板块轮动：最近一周 vs 之前的板块提及变化"""
        sent_map = {o["post_id"]: o for o in opinions}
        now = datetime.now()
        recent, prev = Counter(), Counter()
        for p in posts:
            dt = _safe_date(p.get("created_at"))
            if not dt:
                continue
            o = sent_map.get(p["post_id"])
            if not o:
                continue
            sectors = [s for s in (o.get("sectors") or "").split(",") if s]
            days = (now - dt).days
            for sec in sectors:
                if days <= 7:
                    recent[sec] += 1
                elif days <= 14:
                    prev[sec] += 1

        gaining, losing = [], []
        all_secs = set(recent) | set(prev)
        for sec in all_secs:
            delta = recent.get(sec, 0) - prev.get(sec, 0)
            if delta >= 2:
                gaining.append(sec)
            elif delta <= -2:
                losing.append(sec)
        return {"gaining": gaining[:5], "losing": losing[:5]}

    def _signal_summary(self, bsi, mhi, ci, sm, rai):
        """根据指标生成信号综述"""
        parts = []
        # 情绪
        if bsi >= 30:
            parts.append(f"博主情绪指数 {bsi}，市场情绪偏乐观")
        elif bsi <= -30:
            parts.append(f"博主情绪指数 {bsi}，市场情绪偏悲观")
        else:
            parts.append(f"博主情绪指数 {bsi}，市场情绪中性")
        # 热度
        if mhi >= 60:
            parts.append(f"市场热度 {mhi} 处于高位，关注度较高")
        elif mhi <= 30:
            parts.append(f"市场热度 {mhi} 偏低，交投清淡")
        else:
            parts.append(f"市场热度 {mhi} 处于中位")
        # 共识
        if ci >= 60:
            parts.append(f"共识指数 {ci}，博主观点分歧较小")
        else:
            parts.append(f"共识指数 {ci}，博主观点存在分歧")
        # 动量
        if sm > 10:
            parts.append(f"情绪动量 +{sm}，情绪正在改善")
        elif sm < -10:
            parts.append(f"情绪动量 {sm}，情绪正在转弱")
        else:
            parts.append(f"情绪动量 {sm}，情绪稳定")
        # 风险偏好
        if rai >= 60:
            parts.append(f"风险偏好 {rai}，博主倾向积极")
        elif rai <= 35:
            parts.append(f"风险偏好 {rai}，博主趋于谨慎")

        return "；".join(parts) + "。"
