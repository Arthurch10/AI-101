"""观点分析模块 - NLP 情感分析 + LLM 深度解读"""

import json
import os
import re

import jieba
import jieba.analyse
from snownlp import SnowNLP

from . import database as db


# 财经领域关键词词典
FINANCE_KEYWORDS = {
    "看多", "看空", "做多", "做空", "牛市", "熊市", "加仓", "减仓",
    "建仓", "清仓", "止损", "止盈", "抄底", "逃顶", "利好", "利空",
    "反弹", "回调", "突破", "支撑", "压力", "放量", "缩量", "涨停",
    "跌停", "板块", "赛道", "龙头", "题材", "主力", "游资", "散户",
    "A股", "港股", "美股", "上证", "深证", "创业板", "科创板",
    "基金", "ETF", "债券", "期货", "期权", "外汇", "黄金", "原油",
    "央行", "降息", "加息", "降准", "MLF", "LPR", "GDP", "CPI", "PMI",
    "新能源", "半导体", "消费", "医药", "银行", "地产", "科技",
}

# 市场方向映射
BULLISH_WORDS = {"看多", "做多", "加仓", "建仓", "牛市", "利好", "抄底", "反弹", "突破", "放量"}
BEARISH_WORDS = {"看空", "做空", "减仓", "清仓", "熊市", "利空", "逃顶", "回调", "跌停"}


class OpinionAnalyzer:
    """微博财经观点分析器"""

    def __init__(self, llm_api_key=None, llm_base_url=None, llm_model=None):
        self.llm_api_key = llm_api_key or os.getenv("OPENAI_API_KEY", "")
        self.llm_base_url = llm_base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.llm_model = llm_model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        # 加载财经词汇到 jieba
        for word in FINANCE_KEYWORDS:
            jieba.add_word(word)

    # ------------------------------------------------------------------
    # 基础 NLP 分析 (离线，无需 API)
    # ------------------------------------------------------------------

    def analyze_sentiment(self, text):
        """使用 SnowNLP 进行情感分析，返回 -1 ~ 1"""
        try:
            s = SnowNLP(text)
            # SnowNLP 返回 0~1，映射到 -1~1
            return round(s.sentiments * 2 - 1, 4)
        except Exception:
            return 0.0

    def extract_keywords(self, text, top_k=10):
        """使用 TF-IDF 提取关键词"""
        keywords = jieba.analyse.extract_tags(text, topK=top_k, withWeight=True)
        return keywords

    def detect_market_view(self, text):
        """基于关键词检测市场观点方向"""
        words = set(jieba.cut(text))
        bull_count = len(words & BULLISH_WORDS)
        bear_count = len(words & BEARISH_WORDS)

        if bull_count > bear_count:
            return "bullish"
        elif bear_count > bull_count:
            return "bearish"
        return "neutral"

    def extract_sectors(self, text):
        """提取提及的行业/板块"""
        sector_keywords = {
            "新能源", "半导体", "消费", "医药", "银行", "地产", "科技",
            "军工", "农业", "汽车", "化工", "钢铁", "煤炭", "有色",
            "电力", "传媒", "通信", "计算机", "电子", "机械", "建材",
            "纺织", "食品", "白酒", "光伏", "风电", "储能", "锂电",
            "芯片", "AI", "人工智能", "大模型", "机器人", "低空经济",
        }
        words = set(jieba.cut(text))
        found = words & sector_keywords
        return list(found)

    def extract_tickers(self, text):
        """提取股票代码或名称"""
        # 匹配六位股票代码
        codes = re.findall(r'[（(]?(\d{6})[）)]?', text)
        # 匹配 $XX$ 格式
        dollar_tickers = re.findall(r'\$(.+?)\$', text)
        return list(set(codes + dollar_tickers))

    def analyze_post_basic(self, post):
        """基础分析（不使用 LLM）"""
        text = post["content"]
        sentiment = self.analyze_sentiment(text)
        keywords = self.extract_keywords(text)
        market_view = self.detect_market_view(text)
        sectors = self.extract_sectors(text)
        tickers = self.extract_tickers(text)

        return {
            "post_id": post["post_id"],
            "blogger_uid": post["blogger_uid"],
            "sentiment": sentiment,
            "keywords": ",".join([k for k, _ in keywords]),
            "market_view": market_view,
            "sectors": ",".join(sectors),
            "tickers": ",".join(tickers),
            "confidence": abs(sentiment) * 0.7 + (0.3 if market_view != "neutral" else 0.0),
        }

    # ------------------------------------------------------------------
    # LLM 深度分析
    # ------------------------------------------------------------------

    def analyze_post_with_llm(self, post):
        """使用 LLM 进行深度分析"""
        if not self.llm_api_key:
            return self.analyze_post_basic(post)

        try:
            import openai
            client = openai.OpenAI(
                api_key=self.llm_api_key,
                base_url=self.llm_base_url,
            )

            prompt = f"""分析以下微博财经博主的帖子，以 JSON 格式返回分析结果：

帖子内容: {post['content']}

请返回如下 JSON：
{{
    "sentiment": <float, -1到1, 负数看空正数看多>,
    "market_view": "<bullish/bearish/neutral>",
    "sectors": ["<涉及的板块>"],
    "tickers": ["<涉及的股票代码或名称>"],
    "key_points": ["<核心观点，最多3条>"],
    "confidence": <float, 0到1, 判断的置信度>,
    "risk_warning": "<风险提示>"
}}

仅返回 JSON，不要其他内容。"""

            response = client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "你是一个专业的财经分析助手，擅长分析微博财经内容。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            result_text = response.choices[0].message.content.strip()
            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "post_id": post["post_id"],
                    "blogger_uid": post["blogger_uid"],
                    "sentiment": result.get("sentiment", 0),
                    "keywords": ",".join(result.get("key_points", [])),
                    "market_view": result.get("market_view", "neutral"),
                    "sectors": ",".join(result.get("sectors", [])),
                    "tickers": ",".join(result.get("tickers", [])),
                    "confidence": result.get("confidence", 0.5),
                }
        except Exception as e:
            print(f"  [LLM分析失败] {e}，回退到基础分析")

        return self.analyze_post_basic(post)

    # ------------------------------------------------------------------
    # 批量分析
    # ------------------------------------------------------------------

    def analyze_unprocessed(self, use_llm=False):
        """分析所有未处理的帖子"""
        posts = db.get_unanalyzed_posts(limit=50)
        results = []
        for post in posts:
            if use_llm:
                opinion = self.analyze_post_with_llm(post)
            else:
                opinion = self.analyze_post_basic(post)
            db.save_opinion(opinion)
            results.append(opinion)
        return results

    def get_blogger_summary(self, uid):
        """获取博主的历史观点汇总"""
        opinions = db.get_opinions(uid, limit=200)
        if not opinions:
            return None

        sentiments = [o["sentiment"] for o in opinions if o["sentiment"] is not None]
        views = [o["market_view"] for o in opinions if o["market_view"]]

        # 统计各方向占比
        bull_count = views.count("bullish")
        bear_count = views.count("bearish")
        neutral_count = views.count("neutral")
        total = len(views) or 1

        # 收集所有提及的板块和个股
        all_sectors = []
        all_tickers = []
        for o in opinions:
            if o["sectors"]:
                all_sectors.extend(o["sectors"].split(","))
            if o["tickers"]:
                all_tickers.extend(o["tickers"].split(","))

        # 统计频次
        from collections import Counter
        sector_freq = Counter(s for s in all_sectors if s)
        ticker_freq = Counter(t for t in all_tickers if t)

        return {
            "uid": uid,
            "total_opinions": len(opinions),
            "avg_sentiment": round(sum(sentiments) / len(sentiments), 4) if sentiments else 0,
            "bullish_pct": round(bull_count / total * 100, 1),
            "bearish_pct": round(bear_count / total * 100, 1),
            "neutral_pct": round(neutral_count / total * 100, 1),
            "top_sectors": sector_freq.most_common(10),
            "top_tickers": ticker_freq.most_common(10),
            "recent_view": views[0] if views else "unknown",
            "avg_confidence": round(
                sum(o["confidence"] for o in opinions if o["confidence"]) / len(opinions), 4
            ),
        }

    def generate_investment_brief(self, blogger_uids=None):
        """生成综合投资摘要"""
        if not blogger_uids:
            bloggers = db.get_all_bloggers()
            blogger_uids = [b["uid"] for b in bloggers]

        summaries = []
        for uid in blogger_uids:
            summary = self.get_blogger_summary(uid)
            if summary:
                blogger = db.get_blogger(uid)
                summary["screen_name"] = blogger["screen_name"] if blogger else uid
                summaries.append(summary)

        return summaries
