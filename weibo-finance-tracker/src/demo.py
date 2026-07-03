"""演示模式 - 使用模拟数据展示完整工作流"""

from datetime import datetime, timedelta
import random

from . import database as db


DEMO_BLOGGERS = [
    {
        "uid": "1729390673",
        "screen_name": "财经老王",
        "description": "专注A股投资20年，擅长价值投资与趋势分析",
        "followers_count": 1_580_000,
        "statuses_count": 12340,
        "verified": True,
        "verified_reason": "知名财经博主",
    },
    {
        "uid": "2001001001",
        "screen_name": "股市早知道",
        "description": "每日盘前资讯，市场热点追踪",
        "followers_count": 3_200_000,
        "statuses_count": 28900,
        "verified": True,
        "verified_reason": "财经大V",
    },
    {
        "uid": "2001001002",
        "screen_name": "量化小李",
        "description": "量化交易策略分享，数据驱动投资",
        "followers_count": 680_000,
        "statuses_count": 5600,
        "verified": True,
        "verified_reason": "基金经理",
    },
    {
        "uid": "2001001003",
        "screen_name": "半导体观察",
        "description": "芯片半导体行业深度研究",
        "followers_count": 920_000,
        "statuses_count": 8900,
        "verified": True,
        "verified_reason": "行业分析师",
    },
    {
        "uid": "2001001004",
        "screen_name": "新能源投研",
        "description": "新能源赛道深度覆盖，光伏锂电风电",
        "followers_count": 1_100_000,
        "statuses_count": 7200,
        "verified": True,
        "verified_reason": "新能源研究员",
    },
    {
        "uid": "2001001005",
        "screen_name": "消费龙头研究",
        "description": "消费行业专注研究，白酒医药食品",
        "followers_count": 750_000,
        "statuses_count": 6100,
        "verified": True,
        "verified_reason": "消费行业分析师",
    },
    {
        "uid": "2001001006",
        "screen_name": "技术面老张",
        "description": "20年技术分析经验，K线形态与量价关系",
        "followers_count": 2_400_000,
        "statuses_count": 31000,
        "verified": True,
        "verified_reason": "技术分析专家",
    },
    {
        "uid": "2001001007",
        "screen_name": "宏观经济眼",
        "description": "宏观经济分析，政策解读，全球市场联动",
        "followers_count": 1_850_000,
        "statuses_count": 9800,
        "verified": True,
        "verified_reason": "经济学博士",
    },
]

DEMO_POSTS_TEMPLATES = [
    {
        "content": "今天A股放量上涨，上证突破3400点，成交额突破万亿。#A股# 主力资金大幅流入半导体和新能源板块，看多后市，建议逢低加仓科技股。$宁德时代$ $中芯国际$",
        "market_view": "bullish",
        "reposts": (500, 2000),
        "comments": (200, 800),
        "attitudes": (1000, 5000),
    },
    {
        "content": "央行今日降准50个基点，释放长期资金约1万亿元。#降准# 利好银行和地产板块，但需关注汇率压力。短期看多，中期仍需观察经济数据。",
        "market_view": "bullish",
        "reposts": (800, 3000),
        "comments": (300, 1200),
        "attitudes": (2000, 8000),
    },
    {
        "content": "美联储加息预期升温，外资持续流出A股。#美联储# 今天北向资金净卖出超80亿，市场情绪偏弱。建议减仓观望，等待方向明朗。看空短期走势。",
        "market_view": "bearish",
        "reposts": (300, 1500),
        "comments": (150, 600),
        "attitudes": (500, 3000),
    },
    {
        "content": "光伏板块迎来政策利好！发改委发布新能源发展规划，2025年装机目标上调。#光伏# #新能源# 龙头隆基绿能、通威股份值得关注，做多新能源赛道。$隆基绿能$ $通威股份$",
        "market_view": "bullish",
        "reposts": (600, 2500),
        "comments": (250, 900),
        "attitudes": (1500, 6000),
    },
    {
        "content": "AI大模型持续发酵，算力需求暴增。#AI# #人工智能# 英伟达财报超预期，A股算力概念有望受益。关注中际旭创、工业富联等。但估值偏高，追高需谨慎。",
        "market_view": "bullish",
        "reposts": (700, 2800),
        "comments": (300, 1000),
        "attitudes": (2000, 7000),
    },
    {
        "content": "房地产调控政策再收紧，多地上调首付比例。#地产# 地产板块集体大跌，万科A跌超5%。看空地产板块，短期建议回避。资金或转向科技和消费。",
        "market_view": "bearish",
        "reposts": (400, 1800),
        "comments": (200, 700),
        "attitudes": (800, 4000),
    },
    {
        "content": "白酒板块今天逆势上涨，茅台创历史新高。#白酒# 消费复苏逻辑持续验证，看多消费龙头。$贵州茅台$ $五粮液$ 长期持有不动摇。",
        "market_view": "bullish",
        "reposts": (900, 3500),
        "comments": (400, 1500),
        "attitudes": (3000, 10000),
    },
    {
        "content": "今日大盘缩量震荡，两市成交额不足8000亿。#A股# 市场缺乏主线，板块轮动加速。中性观望为主，不追高不杀跌，耐心等待机会。",
        "market_view": "neutral",
        "reposts": (200, 1000),
        "comments": (100, 500),
        "attitudes": (400, 2000),
    },
    {
        "content": "半导体设备国产替代加速！中芯国际产能利用率回升至90%。#半导体# #芯片# 看多国产芯片产业链，重点关注设备和材料环节。$北方华创$ $中微公司$",
        "market_view": "bullish",
        "reposts": (500, 2200),
        "comments": (200, 800),
        "attitudes": (1200, 5500),
    },
    {
        "content": "注意风险！创业板指已经连续上涨8天，技术面严重超买。#创业板# MACD顶背离信号明显，RSI超过80。短期看空，建议止盈减仓，不要追高。",
        "market_view": "bearish",
        "reposts": (600, 2000),
        "comments": (250, 900),
        "attitudes": (1000, 4500),
    },
    {
        "content": "低空经济概念持续活跃，eVTOL产业链迎来爆发期。#低空经济# 多地出台支持政策，2025年有望成为低空经济元年。关注万丰奥威、中信海直。做多低空概念。",
        "market_view": "bullish",
        "reposts": (400, 1600),
        "comments": (180, 700),
        "attitudes": (800, 3500),
    },
    {
        "content": "医药板块持续调整，集采压力下创新药企业承压。#医药# 短期看空医药，但长期关注创新药和CXO龙头的估值修复机会。$药明康德$ $恒瑞医药$",
        "market_view": "bearish",
        "reposts": (300, 1200),
        "comments": (150, 550),
        "attitudes": (600, 2800),
    },
]


def load_demo_data():
    """加载演示数据"""
    db.init_db()

    # 添加博主
    for b in DEMO_BLOGGERS:
        db.add_blogger(
            uid=b["uid"],
            screen_name=b["screen_name"],
            description=b["description"],
            followers_count=b["followers_count"],
            statuses_count=b["statuses_count"],
            verified=b["verified"],
            verified_reason=b["verified_reason"],
            manual_selected=(b["uid"] == "1729390673"),
        )

    # 为每个博主生成帖子
    now = datetime.now()
    post_id_counter = 5000000000

    for blogger in DEMO_BLOGGERS:
        uid = blogger["uid"]
        # 每个博主 8-12 条帖子
        num_posts = random.randint(8, 12)
        selected_templates = random.sample(
            DEMO_POSTS_TEMPLATES, min(num_posts, len(DEMO_POSTS_TEMPLATES))
        )

        for j, template in enumerate(selected_templates):
            post_id_counter += 1
            days_ago = random.randint(0, 25)
            hours_ago = random.randint(0, 23)
            created = now - timedelta(days=days_ago, hours=hours_ago)

            post = {
                "post_id": str(post_id_counter),
                "blogger_uid": uid,
                "content": template["content"],
                "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
                "reposts_count": random.randint(*template["reposts"]),
                "comments_count": random.randint(*template["comments"]),
                "attitudes_count": random.randint(*template["attitudes"]),
                "topics": "",
            }
            db.save_posts([post])

    return len(DEMO_BLOGGERS)
