"""pytest 共享配置 - 每个测试使用隔离的临时数据库"""

import pytest

from src import database as db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """把数据库指向临时文件，保证测试互不干扰"""
    dbfile = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(dbfile))
    db.init_db()
    yield


@pytest.fixture
def sample_blogger():
    db.add_blogger(
        uid="1001", screen_name="测试博主", description="财经",
        followers_count=500000, statuses_count=100,
        verified=True, verified_reason="财经大V", manual_selected=True,
    )
    return "1001"


def add_post(post_id, uid, content, created_at, **kw):
    """测试辅助: 插入一条帖子"""
    db.save_posts([{
        "post_id": post_id, "blogger_uid": uid, "content": content,
        "created_at": created_at,
        "reposts_count": kw.get("reposts", 10),
        "comments_count": kw.get("comments", 5),
        "attitudes_count": kw.get("attitudes", 20),
        "topics": kw.get("topics", ""),
    }])
