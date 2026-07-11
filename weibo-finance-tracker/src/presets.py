"""精选大 V 池 - 供用户从推荐名单一键自选添加

说明: 这是一批覆盖不同领域的**演示大 V**（昵称为示例），用于在无法访问
微博搜索接口时也能自主选择、体验完整流程。真实使用时可用 wft blogger add
<UID或昵称> 添加真实博主。
"""

from . import database as db
from .demo import DEMO_BLOGGERS, generate_posts_for_blogger
from .analyzer import OpinionAnalyzer


# 额外的精选大 V（覆盖更多领域）
EXTRA_PRESETS = [
    {"uid": "2001002001", "screen_name": "港股猎手", "field": "港股",
     "description": "港股打新与南向资金追踪", "followers_count": 830000,
     "verified_reason": "港股分析师"},
    {"uid": "2001002002", "screen_name": "美股老兵", "field": "美股",
     "description": "美股科技股与纳指策略", "followers_count": 1240000,
     "verified_reason": "海外市场研究"},
    {"uid": "2001002003", "screen_name": "可转债打新", "field": "可转债",
     "description": "可转债申购与低吸策略", "followers_count": 560000,
     "verified_reason": "固收投资人"},
    {"uid": "2001002004", "screen_name": "ETF定投君", "field": "ETF/基金",
     "description": "宽基与行业 ETF 定投", "followers_count": 690000,
     "verified_reason": "基金投顾"},
    {"uid": "2001002005", "screen_name": "期货老炮", "field": "期货",
     "description": "商品期货与股指期货", "followers_count": 470000,
     "verified_reason": "期货分析师"},
    {"uid": "2001002006", "screen_name": "游资情报站", "field": "短线/游资",
     "description": "龙虎榜与涨停复盘", "followers_count": 1560000,
     "verified_reason": "短线复盘"},
    {"uid": "2001002007", "screen_name": "政策风向标", "field": "政策",
     "description": "政策解读与主题投资", "followers_count": 980000,
     "verified_reason": "政策研究"},
    {"uid": "2001002008", "screen_name": "红利价投", "field": "价值/红利",
     "description": "高股息与红利资产配置", "followers_count": 720000,
     "verified_reason": "价值投资人"},
]


def _demo_with_field():
    """给演示博主补上领域标签"""
    field_map = {
        "财经老王": "综合/A股", "股市早知道": "资讯", "量化小李": "量化",
        "半导体观察": "半导体", "新能源投研": "新能源", "消费龙头研究": "消费",
        "技术面老张": "技术分析", "宏观经济眼": "宏观",
    }
    out = []
    for b in DEMO_BLOGGERS:
        item = dict(b)
        item["field"] = field_map.get(b["screen_name"], "综合")
        out.append(item)
    return out


def list_presets():
    """返回全部精选大 V（含是否已加入库的标记）"""
    presets = _demo_with_field() + EXTRA_PRESETS
    existing = {b["uid"] for b in db.get_all_bloggers()}
    result = []
    for p in presets:
        result.append({
            "uid": p["uid"],
            "screen_name": p["screen_name"],
            "field": p.get("field", "综合"),
            "description": p.get("description", ""),
            "followers_count": p.get("followers_count", 0),
            "verified_reason": p.get("verified_reason", ""),
            "added": p["uid"] in existing,
        })
    return result


def add_preset(uid, manual=False, with_posts=True, analyze=True):
    """把精选大 V 加入追踪库；可选生成演示帖子并分析，便于立即体验"""
    presets = {p["uid"]: p for p in (_demo_with_field() + EXTRA_PRESETS)}
    p = presets.get(uid)
    if not p:
        return None

    db.add_blogger(
        uid=p["uid"], screen_name=p["screen_name"],
        description=p.get("description", ""),
        followers_count=p.get("followers_count", 0),
        statuses_count=p.get("statuses_count", 0),
        verified=True, verified_reason=p.get("verified_reason", ""),
        manual_selected=manual,
    )
    if with_posts and db.get_blogger_post_count(uid) == 0:
        generate_posts_for_blogger(uid)
    if analyze:
        OpinionAnalyzer().analyze_unprocessed(use_llm=False)
    return db.get_blogger(uid)
