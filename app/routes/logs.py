#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""操作日志路由 + 写日志工具函数"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends

from auth import require_login
from database import get_db, ACTION_LOG

router = APIRouter(tags=["日志"])


def log_action(
    user: dict,
    action: str,
    item_id: Optional[int] = None,
    item_name: str = "",
    old_value: str = "",
    new_value: str = "",
    detail: str = "",
):
    """写操作日志（数据库 + 文件）"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO action_logs
               (user_id, user_name, action, item_id, item_name, old_value, new_value, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], user["name"], action, item_id, item_name,
             str(old_value), str(new_value), detail),
        )
    line = f"[{datetime.now().isoformat()}] {user['name']}({user['id']}) {action} {item_name} {old_value}→{new_value} {detail}\n"
    try:
        with open(ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


@router.get("/api/logs")
async def list_logs(limit: int = 100, user: dict = Depends(require_login)):
    limit = min(max(limit, 1), 500)  # 限制在 1-500 之间
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM action_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
