"""SQLite 数据库管理模块 - 存储博主信息、帖子和分析结果"""

import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "weibo_finance.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS bloggers (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        uid             TEXT UNIQUE NOT NULL,
        screen_name     TEXT NOT NULL,
        description     TEXT,
        followers_count INTEGER DEFAULT 0,
        statuses_count  INTEGER DEFAULT 0,
        verified        INTEGER DEFAULT 0,
        verified_reason TEXT,
        added_at        TEXT DEFAULT (datetime('now')),
        is_active       INTEGER DEFAULT 1,
        manual_selected INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS posts (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id         TEXT UNIQUE NOT NULL,
        blogger_uid     TEXT NOT NULL,
        content         TEXT NOT NULL,
        created_at      TEXT,
        reposts_count   INTEGER DEFAULT 0,
        comments_count  INTEGER DEFAULT 0,
        attitudes_count INTEGER DEFAULT 0,
        topics          TEXT,
        fetched_at      TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (blogger_uid) REFERENCES bloggers(uid)
    );

    CREATE TABLE IF NOT EXISTS opinions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id         TEXT NOT NULL,
        blogger_uid     TEXT NOT NULL,
        sentiment       REAL,
        keywords        TEXT,
        market_view     TEXT,
        sectors         TEXT,
        tickers         TEXT,
        confidence      REAL DEFAULT 0.0,
        analyzed_at     TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (post_id)     REFERENCES posts(post_id),
        FOREIGN KEY (blogger_uid) REFERENCES bloggers(uid)
    );

    CREATE TABLE IF NOT EXISTS rankings (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        blogger_uid     TEXT NOT NULL,
        score           REAL NOT NULL,
        accuracy_score  REAL DEFAULT 0.0,
        influence_score REAL DEFAULT 0.0,
        activity_score  REAL DEFAULT 0.0,
        consistency_score REAL DEFAULT 0.0,
        ranked_at       TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (blogger_uid) REFERENCES bloggers(uid)
    );

    CREATE INDEX IF NOT EXISTS idx_posts_blogger   ON posts(blogger_uid);
    CREATE INDEX IF NOT EXISTS idx_posts_created    ON posts(created_at);
    CREATE INDEX IF NOT EXISTS idx_opinions_blogger ON opinions(blogger_uid);
    CREATE INDEX IF NOT EXISTS idx_rankings_score   ON rankings(score DESC);
    """)
    conn.commit()
    conn.close()


# ---------- Blogger CRUD ----------

def add_blogger(uid, screen_name, description="", followers_count=0,
                statuses_count=0, verified=False, verified_reason="",
                manual_selected=False):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO bloggers
            (uid, screen_name, description, followers_count, statuses_count,
             verified, verified_reason, manual_selected)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (uid, screen_name, description, followers_count, statuses_count,
          int(verified), verified_reason, int(manual_selected)))
    conn.commit()
    conn.close()


def get_all_bloggers(active_only=True):
    conn = get_connection()
    query = "SELECT * FROM bloggers"
    if active_only:
        query += " WHERE is_active = 1"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_blogger(uid):
    conn = get_connection()
    row = conn.execute("SELECT * FROM bloggers WHERE uid = ?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def remove_blogger(uid):
    conn = get_connection()
    conn.execute("UPDATE bloggers SET is_active = 0 WHERE uid = ?", (uid,))
    conn.commit()
    conn.close()


# ---------- Posts CRUD ----------

def save_posts(posts_list):
    conn = get_connection()
    conn.executemany("""
        INSERT OR IGNORE INTO posts
            (post_id, blogger_uid, content, created_at,
             reposts_count, comments_count, attitudes_count, topics)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [(p["post_id"], p["blogger_uid"], p["content"], p["created_at"],
           p.get("reposts_count", 0), p.get("comments_count", 0),
           p.get("attitudes_count", 0), p.get("topics", ""))
          for p in posts_list])
    conn.commit()
    conn.close()


def get_posts(blogger_uid=None, limit=100, offset=0):
    conn = get_connection()
    if blogger_uid:
        rows = conn.execute(
            "SELECT * FROM posts WHERE blogger_uid = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (blogger_uid, limit, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unanalyzed_posts(limit=50):
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.* FROM posts p
        LEFT JOIN opinions o ON p.post_id = o.post_id
        WHERE o.id IS NULL
        ORDER BY p.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Opinions CRUD ----------

def save_opinion(opinion):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO opinions
            (post_id, blogger_uid, sentiment, keywords, market_view,
             sectors, tickers, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (opinion["post_id"], opinion["blogger_uid"], opinion["sentiment"],
          opinion["keywords"], opinion["market_view"], opinion["sectors"],
          opinion["tickers"], opinion["confidence"]))
    conn.commit()
    conn.close()


def get_opinions(blogger_uid=None, limit=100):
    conn = get_connection()
    if blogger_uid:
        rows = conn.execute(
            "SELECT * FROM opinions WHERE blogger_uid = ? ORDER BY analyzed_at DESC LIMIT ?",
            (blogger_uid, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM opinions ORDER BY analyzed_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Rankings ----------

def save_ranking(ranking):
    conn = get_connection()
    conn.execute("""
        INSERT INTO rankings
            (blogger_uid, score, accuracy_score, influence_score,
             activity_score, consistency_score)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ranking["blogger_uid"], ranking["score"], ranking["accuracy_score"],
          ranking["influence_score"], ranking["activity_score"],
          ranking["consistency_score"]))
    conn.commit()
    conn.close()


def get_latest_rankings(top_n=10):
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.*, b.screen_name, b.followers_count, b.verified
        FROM rankings r
        JOIN bloggers b ON r.blogger_uid = b.uid
        WHERE r.ranked_at = (SELECT MAX(ranked_at) FROM rankings)
        ORDER BY r.score DESC
        LIMIT ?
    """, (top_n,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_blogger_post_count(uid):
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM posts WHERE blogger_uid = ?", (uid,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0
