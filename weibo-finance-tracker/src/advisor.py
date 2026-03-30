"""投资辅助模块 - 基于博主观点生成投资建议"""

import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta

from . import database as db
from .analyzer import OpinionAnalyzer


class InvestmentAdvisor:
    """投资辅助顾问 - 聚合博主观点，生成投资参考"""

    def __init__(self, llm_api_key=None, llm_base_url=None, llm_model=None):
        self.llm_api_key = llm_api_key or os.getenv("OPENAI_API_KEY", "")
        self.llm_base_url = llm_base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.llm_model = llm_model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.analyzer = OpinionAnalyzer(llm_api_key, llm_base_url, llm_model)

    def get_market_consensus(self, blogger_uids=None, days=7):
        """
        获取市场共识：聚合多位博主的观点

        返回:
            dict: 市场情绪共识、热门板块、关注个股等
        """
        if not blogger_uids:
            bloggers = db.get_all_bloggers()
            blogger_uids = [b["uid"] for b in bloggers]

        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        all_opinions = []
        for uid in blogger_uids:
            opinions = db.get_opinions(uid, limit=100)
            recent = [o for o in opinions if o.get("analyzed_at", "") >= cutoff]
            all_opinions.extend(recent)

        if not all_opinions:
            return {"error": "没有足够的近期观点数据，请先运行数据采集和分析"}

        # 情绪统计
        sentiments = [o["sentiment"] for o in all_opinions if o["sentiment"] is not None]
        views = [o["market_view"] for o in all_opinions if o["market_view"]]
        bull = views.count("bullish")
        bear = views.count("bearish")
        total = len(views) or 1

        # 板块热度
        all_sectors = []
        all_tickers = []
        for o in all_opinions:
            if o["sectors"]:
                all_sectors.extend(o["sectors"].split(","))
            if o["tickers"]:
                all_tickers.extend(o["tickers"].split(","))

        sector_freq = Counter(s for s in all_sectors if s)
        ticker_freq = Counter(t for t in all_tickers if t)

        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        # 判断市场共识
        if bull / total > 0.6:
            consensus = "偏多"
        elif bear / total > 0.6:
            consensus = "偏空"
        elif bull / total > 0.4 and bear / total > 0.4:
            consensus = "分歧较大"
        else:
            consensus = "中性观望"

        return {
            "period_days": days,
            "total_opinions": len(all_opinions),
            "consensus": consensus,
            "avg_sentiment": round(avg_sentiment, 4),
            "bullish_pct": round(bull / total * 100, 1),
            "bearish_pct": round(bear / total * 100, 1),
            "hot_sectors": sector_freq.most_common(10),
            "hot_tickers": ticker_freq.most_common(10),
            "blogger_count": len(blogger_uids),
        }

    def generate_advice(self, blogger_uids=None, days=7):
        """
        生成投资建议报告

        结合市场共识 + 博主分析 + LLM 生成建议
        """
        consensus = self.get_market_consensus(blogger_uids, days)
        if "error" in consensus:
            return consensus

        summaries = self.analyzer.generate_investment_brief(blogger_uids)

        report = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_consensus": consensus,
            "blogger_summaries": summaries,
            "advice": None,
        }

        # 生成基础建议（无需 LLM）
        basic_advice = self._generate_basic_advice(consensus, summaries)
        report["advice"] = basic_advice

        # 如果有 LLM API，生成更详细的建议
        if self.llm_api_key:
            llm_advice = self._generate_llm_advice(consensus, summaries)
            if llm_advice:
                report["advice"] = llm_advice

        return report

    def _generate_basic_advice(self, consensus, summaries):
        """基于规则生成基础投资建议"""
        advice_lines = []

        # 1) 市场整体判断
        advice_lines.append(f"【市场情绪】 {consensus['consensus']}")
        advice_lines.append(
            f"  看多 {consensus['bullish_pct']}% | 看空 {consensus['bearish_pct']}% "
            f"(基于 {consensus['total_opinions']} 条观点)"
        )

        # 2) 热门板块
        if consensus["hot_sectors"]:
            sectors = [f"{s}({c}次)" for s, c in consensus["hot_sectors"][:5]]
            advice_lines.append(f"【热门板块】 {' | '.join(sectors)}")

        # 3) 关注个股
        if consensus["hot_tickers"]:
            tickers = [f"{t}({c}次)" for t, c in consensus["hot_tickers"][:5]]
            advice_lines.append(f"【关注个股】 {' | '.join(tickers)}")

        # 4) 操作建议
        sent = consensus["avg_sentiment"]
        if sent > 0.3:
            advice_lines.append("【操作建议】 博主整体偏乐观，可关注热门板块的回调机会")
        elif sent < -0.3:
            advice_lines.append("【操作建议】 博主整体偏悲观，建议谨慎操作，控制仓位")
        else:
            advice_lines.append("【操作建议】 市场观点分歧，建议观望为主，等待方向明朗")

        # 5) 博主一致看好的方向
        if summaries:
            bullish_bloggers = [s for s in summaries if s.get("avg_sentiment", 0) > 0.2]
            if bullish_bloggers:
                names = [s["screen_name"] for s in bullish_bloggers[:3]]
                advice_lines.append(f"【偏多博主】 {', '.join(names)}")

            bearish_bloggers = [s for s in summaries if s.get("avg_sentiment", 0) < -0.2]
            if bearish_bloggers:
                names = [s["screen_name"] for s in bearish_bloggers[:3]]
                advice_lines.append(f"【偏空博主】 {', '.join(names)}")

        # 6) 风险提示
        advice_lines.append("")
        advice_lines.append("⚠️ 风险提示：以上分析仅基于微博博主观点汇总，不构成投资建议。"
                          "投资有风险，入市需谨慎。请结合自身情况独立判断。")

        return "\n".join(advice_lines)

    def _generate_llm_advice(self, consensus, summaries):
        """使用 LLM 生成详细投资建议"""
        try:
            import openai
            client = openai.OpenAI(
                api_key=self.llm_api_key,
                base_url=self.llm_base_url,
            )

            context = json.dumps({
                "market_consensus": {
                    "consensus": consensus["consensus"],
                    "avg_sentiment": consensus["avg_sentiment"],
                    "bullish_pct": consensus["bullish_pct"],
                    "bearish_pct": consensus["bearish_pct"],
                    "hot_sectors": consensus["hot_sectors"][:5],
                    "hot_tickers": consensus["hot_tickers"][:5],
                },
                "blogger_summaries": [
                    {
                        "name": s["screen_name"],
                        "avg_sentiment": s["avg_sentiment"],
                        "bullish_pct": s["bullish_pct"],
                        "top_sectors": s["top_sectors"][:3],
                        "recent_view": s["recent_view"],
                    }
                    for s in summaries[:5]
                ],
            }, ensure_ascii=False, indent=2)

            prompt = f"""基于以下微博财经博主的观点汇总数据，生成一份简洁的投资参考报告。

数据:
{context}

要求：
1. 用中文输出
2. 包含：市场情绪判断、热门板块分析、操作建议、风险提示
3. 语言简洁专业，控制在 500 字以内
4. 必须包含风险提示：以上分析基于微博博主观点，不构成投资建议
"""

            response = client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "你是一个专业的投资分析助手。基于多位财经博主的观点汇总，生成客观的投资参考报告。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=800,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"  [LLM建议生成失败] {e}")
            return None
