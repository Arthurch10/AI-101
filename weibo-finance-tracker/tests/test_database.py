"""数据库 CRUD 测试"""

from src import database as db


def test_add_and_get_blogger():
    db.add_blogger(uid="42", screen_name="张三", followers_count=1000)
    b = db.get_blogger("42")
    assert b is not None
    assert b["screen_name"] == "张三"
    assert b["followers_count"] == 1000


def test_add_blogger_replace():
    db.add_blogger(uid="42", screen_name="张三", followers_count=1000)
    db.add_blogger(uid="42", screen_name="张三改", followers_count=2000)
    b = db.get_blogger("42")
    assert b["screen_name"] == "张三改"
    assert b["followers_count"] == 2000


def test_remove_blogger_soft_delete():
    db.add_blogger(uid="42", screen_name="张三")
    db.remove_blogger("42")
    assert db.get_blogger("42")["is_active"] == 0
    assert all(b["uid"] != "42" for b in db.get_all_bloggers())


def test_save_and_get_posts():
    db.add_blogger(uid="1", screen_name="A")
    db.save_posts([{
        "post_id": "p1", "blogger_uid": "1", "content": "hello",
        "created_at": "2026-01-01 10:00:00",
        "reposts_count": 1, "comments_count": 2, "attitudes_count": 3, "topics": "",
    }])
    posts = db.get_posts("1")
    assert len(posts) == 1
    assert posts[0]["content"] == "hello"
    assert db.get_blogger_post_count("1") == 1


def test_posts_dedup_by_id():
    db.add_blogger(uid="1", screen_name="A")
    post = {"post_id": "p1", "blogger_uid": "1", "content": "x",
            "created_at": "2026-01-01 10:00:00",
            "reposts_count": 0, "comments_count": 0, "attitudes_count": 0, "topics": ""}
    db.save_posts([post])
    db.save_posts([post])  # 重复插入应被忽略
    assert db.get_blogger_post_count("1") == 1


def test_save_and_get_backtest():
    db.add_blogger(uid="1", screen_name="A")
    db.save_backtest("1", accuracy=0.75, evaluated=8, correct=6)
    bt = db.get_backtest("1")
    assert bt["accuracy"] == 0.75
    assert bt["evaluated"] == 8
    assert bt["correct"] == 6


def test_unanalyzed_posts():
    db.add_blogger(uid="1", screen_name="A")
    db.save_posts([{"post_id": "p1", "blogger_uid": "1", "content": "x",
                    "created_at": "2026-01-01 10:00:00",
                    "reposts_count": 0, "comments_count": 0,
                    "attitudes_count": 0, "topics": ""}])
    assert len(db.get_unanalyzed_posts()) == 1
    db.save_opinion({"post_id": "p1", "blogger_uid": "1", "sentiment": 0.5,
                     "keywords": "", "market_view": "bullish", "sectors": "",
                     "tickers": "", "confidence": 0.5})
    assert len(db.get_unanalyzed_posts()) == 0
