"""精选大 V 池与 AI 观点流测试"""

from src import database as db
from src import presets


def test_list_presets_has_fields():
    pool = presets.list_presets()
    assert len(pool) >= 12
    # 每项含必要字段
    for p in pool:
        assert p["uid"] and p["screen_name"] and p["field"]
        assert "added" in p


def test_add_preset_creates_blogger_and_posts():
    pool = presets.list_presets()
    target = next(p for p in pool if not p["added"])
    blogger = presets.add_preset(target["uid"])
    assert blogger is not None
    assert db.get_blogger(target["uid"]) is not None
    # 生成了演示帖子
    assert db.get_blogger_post_count(target["uid"]) > 0


def test_add_preset_marks_added():
    pool = presets.list_presets()
    target = next(p for p in pool if not p["added"])
    presets.add_preset(target["uid"])
    pool2 = presets.list_presets()
    added = next(p for p in pool2 if p["uid"] == target["uid"])
    assert added["added"] is True


def test_add_unknown_preset_returns_none():
    assert presets.add_preset("nonexistent_uid") is None


def test_opinion_feed_joins_content_and_ai():
    # 加一个精选大 V（含帖子），分析后取观点流
    pool = presets.list_presets()
    uid = next(p for p in pool if not p["added"])["uid"]
    presets.add_preset(uid)  # 内部已分析

    feed = db.get_opinion_feed([uid], limit=10)
    assert feed
    row = feed[0]
    # 联表字段齐全
    assert "content" in row and row["content"]
    assert "screen_name" in row
    assert "market_view" in row  # 来自 opinions 的 AI 解读


def test_opinion_feed_desc_order():
    pool = presets.list_presets()
    uid = next(p for p in pool if not p["added"])["uid"]
    presets.add_preset(uid)
    feed = db.get_opinion_feed([uid], limit=20)
    dates = [f["created_at"] for f in feed]
    assert dates == sorted(dates, reverse=True)
