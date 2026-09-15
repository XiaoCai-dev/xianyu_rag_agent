"""仪表盘统计：消息数、会话数、意图分布、议价统计、RAG 概况。"""

import sqlite3
from fastapi import APIRouter

from ..deps import get_context_manager, get_rag

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard():
    cm = get_context_manager()
    conn = sqlite3.connect(cm.db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    stats = {}

    # 消息统计
    cur.execute("SELECT COUNT(*) AS n FROM messages")
    stats["total_messages"] = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM messages WHERE date(timestamp)=date('now')")
    stats["today_messages"] = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM messages WHERE role='assistant'")
    stats["bot_replies"] = cur.fetchone()["n"]

    # 会话与商品
    cur.execute("SELECT COUNT(DISTINCT chat_id) AS n FROM messages")
    stats["total_conversations"] = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM items")
    stats["total_items"] = cur.fetchone()["n"]

    # 意图分布（仅 assistant 消息记录了 intent）
    cur.execute("""
        SELECT COALESCE(intent,'unknown') AS intent, COUNT(*) AS n
        FROM messages WHERE role='assistant'
        GROUP BY intent ORDER BY n DESC
    """)
    stats["intent_distribution"] = [dict(r) for r in cur.fetchall()]

    # 议价统计
    cur.execute("SELECT COUNT(*) AS n FROM chat_bargain_counts")
    stats["bargain_conversations"] = cur.fetchone()["n"]
    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM chat_bargain_counts")
    stats["total_bargains"] = cur.fetchone()["s"]

    # 近7天消息趋势
    cur.execute("""
        SELECT date(timestamp) AS day, COUNT(*) AS n
        FROM messages
        WHERE timestamp >= datetime('now','-6 days','start of day')
        GROUP BY day ORDER BY day
    """)
    stats["trend_7d"] = [dict(r) for r in cur.fetchall()]

    conn.close()

    # RAG 概况
    rag = get_rag()
    stats["rag"] = rag.stats() if rag else {"available": False}

    return stats
