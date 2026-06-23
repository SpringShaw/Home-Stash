#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""购物清单路由"""

from typing import Optional

from fastapi import APIRouter, Depends, Form

from auth import require_login
from database import get_db
from logs import log_action

router = APIRouter(tags=["购物清单"])


@router.get("/api/shopping")
async def list_shopping(user: dict = Depends(require_login)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT s.*, i.name as item_name, i.unit, c.name as category_name
            FROM shopping_list s
            LEFT JOIN items i ON s.item_id = i.id
            LEFT JOIN categories c ON i.category_id = c.id
            ORDER BY s.done, s.created_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


@router.post("/api/shopping")
async def add_shopping(
    item_id: Optional[int] = Form(None),
    custom_name: str = Form(""),
    quantity: float = Form(1),
    user: dict = Depends(require_login),
):
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO shopping_list (item_id, custom_name, quantity, user_id, user_name)
               VALUES (?, ?, ?, ?, ?)""",
            (item_id, custom_name, quantity, user["id"], user["name"]),
        )
    log_action(user, "加入购物清单", item_id=item_id, item_name=custom_name or f"item#{item_id}")
    return {"ok": True, "id": cur.lastrowid}


@router.put("/api/shopping/{sid}/done")
async def shopping_done(sid: int, user: dict = Depends(require_login)):
    with get_db() as conn:
        conn.execute("UPDATE shopping_list SET done=1 WHERE id=?", (sid,))
    return {"ok": True}


@router.delete("/api/shopping/{sid}")
async def del_shopping(sid: int, user: dict = Depends(require_login)):
    with get_db() as conn:
        conn.execute("DELETE FROM shopping_list WHERE id=?", (sid,))
    return {"ok": True}
