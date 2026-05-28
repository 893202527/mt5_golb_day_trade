import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "mt5_gold"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

@contextmanager
def get_conn():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def insert_ohlc(row: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO ohlc (symbol, timeframe, bar_time, open, high, low, close, tick_volume, spread)
               VALUES (%(symbol)s, %(tf)s, %(time)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(spread)s)
               ON CONFLICT (symbol, timeframe, bar_time) DO NOTHING""",
            row,
        )

def get_recent_bars(symbol: str, tf: str, limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM ohlc WHERE symbol=%s AND timeframe=%s ORDER BY bar_time DESC LIMIT %s",
            (symbol, tf, limit),
        )
        rows = cur.fetchall()
        return list(rows)[::-1]

def insert_signal(signal: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO signals (bar_time, symbol, timeframe, action, confidence, entry_price, sl, tp, ml_model, llm_response)
               VALUES (%(bar_time)s, %(symbol)s, %(timeframe)s, %(action)s, %(confidence)s, %(entry)s, %(sl)s, %(tp)s, %(ml_model)s, %(llm_response)s)""",
            signal,
        )

def insert_trade(trade: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO trades (signal_id, ticket, symbol, direction, volume, entry_price, sl, tp, entry_time, status)
               VALUES (%(signal_id)s, %(ticket)s, %(symbol)s, %(direction)s, %(volume)s, %(entry_price)s, %(sl)s, %(tp)s, %(entry_time)s, %(status)s)""",
            trade,
        )
