"""会话浏览：列出会话、查看单会话消息历史、查看商品信息。"""

import sqlite3
from fastapi import APIRouter, Query

from ..deps import get_context_manager

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    """分页列出会话概览（按最近活跃排序）。"""
    cm = get_context_manager()
    conn = sqlite3.connect(cm.db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    offset = (page - 1) * size

    cur.execute("""
        SELECT chat_id,
               MAX(timestamp) AS last_active,
               COUNT(*) AS msg_count,
               MAX(CASE WHEN role='user' THEN content END) AS last_user_msg,
               item_id
        FROM messages
        GROUP BY chat_id
        ORDER BY last_active DESC
        LIMIT ? OFFSET ?
    """, (size, offset))
    rows = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT COUNT(DISTINCT chat_id) AS n FROM messages")
    total = cur.fetchone()["n"]
    conn.close()
    return {"items": rows, "total": total, "page": page, "size": size}


@router.get("/{chat_id}")
def get_conversation(chat_id: str):
    """获取单个会话的完整消息历史。"""
    cm = get_context_manager()
    conn = sqlite3.connect(cm.db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, role, content, timestamp, intent
        FROM messages WHERE chat_id=? ORDER BY timestamp ASC
    """, (chat_id,))
    messages = [dict(r) for r in cur.fetchall()]

    # 议价次数
    cur.execute("SELECT count FROM chat_bargain_counts WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    bargain_count = row["count"] if row else 0

    # 商品信息
    cur.execute("SELECT item_id FROM messages WHERE chat_id=? LIMIT 1", (chat_id,))
    mr = cur.fetchone()
    item_info = None
    if mr:
        cur.execute("SELECT item_id, price, description FROM items WHERE item_id=?", (mr["item_id"],))
        ir = cur.fetchone()
        item_info = dict(ir) if ir else None
    conn.close()

    return {"chat_id": chat_id, "messages": messages, "bargain_count": bargain_count, "item": item_info}
