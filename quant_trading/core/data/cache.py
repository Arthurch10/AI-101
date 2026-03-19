"""SQLite 本地缓存，减少对 AKShare 的重复请求。"""
import sqlite3
import os
import pandas as pd
from datetime import datetime, timedelta


def _db_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_file = os.path.join(base, "data", "cache.db")
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    return db_file


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kline_daily (
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                turnover REAL,
                change_pct REAL,
                PRIMARY KEY (symbol, date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_list (
                code TEXT PRIMARY KEY,
                name TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()


def save_kline(symbol: str, df: pd.DataFrame):
    """保存 K 线数据到 SQLite。df 列：date, open, high, low, close, volume, turnover, change_pct"""
    if df.empty:
        return
    with _get_conn() as conn:
        for _, row in df.iterrows():
            conn.execute("""
                INSERT OR REPLACE INTO kline_daily
                (symbol, date, open, high, low, close, volume, turnover, change_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                str(row.get("date", "")),
                float(row.get("open", 0)),
                float(row.get("high", 0)),
                float(row.get("low", 0)),
                float(row.get("close", 0)),
                float(row.get("volume", 0)),
                float(row.get("turnover", 0)),
                float(row.get("change_pct", 0)),
            ))
        conn.commit()


def load_kline(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """从缓存读取 K 线数据。"""
    with _get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM kline_daily WHERE symbol=? AND date>=? AND date<=? ORDER BY date",
            conn, params=(symbol, start_date, end_date)
        )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    return df


def get_cached_date_range(symbol: str):
    """返回缓存中该股票最早和最晚的日期。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT MIN(date), MAX(date) FROM kline_daily WHERE symbol=?", (symbol,)
        ).fetchone()
    return row[0], row[1]


def save_stock_list(df: pd.DataFrame):
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        for _, row in df.iterrows():
            conn.execute(
                "INSERT OR REPLACE INTO stock_list (code, name, updated_at) VALUES (?, ?, ?)",
                (str(row["code"]), str(row["name"]), now)
            )
        conn.commit()


def load_stock_list() -> pd.DataFrame:
    with _get_conn() as conn:
        df = pd.read_sql_query("SELECT code, name FROM stock_list ORDER BY code", conn)
    return df


def is_stock_list_fresh(hours: int = 24) -> bool:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM cache_meta WHERE key='stock_list_updated_at'"
        ).fetchone()
    if not row:
        return False
    updated = datetime.fromisoformat(row[0])
    return datetime.now() - updated < timedelta(hours=hours)


def mark_stock_list_updated():
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache_meta (key, value, updated_at) VALUES (?, ?, ?)",
            ("stock_list_updated_at", datetime.now().isoformat(), datetime.now().isoformat())
        )
        conn.commit()


init_db()
