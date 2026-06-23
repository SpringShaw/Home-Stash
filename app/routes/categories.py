#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分类路由"""

import sqlite3

from fastapi import APIRouter, HTTPException, Depends, Form

from auth import require_login, require_admin
from database import get_db
from logs import log_action

router = APIRouter(tags=["分类"])


@router.get("/api/categories")
async def list_categories(user: dict = Depends(require_login)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT c.id, c.name, c.icon, c.sort_order,
                   COUNT(i.id) as item_count,
                   COALESCE(SUM(CASE WHEN i.stock < i.min_stock THEN 1 ELSE 0 END), 0) as low_count
            FROM categories c
            LEFT JOIN items i ON i.category_id = c.id
            GROUP BY c.id ORDER BY c.sort_order, c.id
        """).fetchall()
    return [dict(r) for r in rows]


@router.post("/api/categories")
async def add_category(
    name: str = Form(..., max_length=100),
    icon: str = Form("📦", max_length=10),
    user: dict = Depends(require_login),
):
    with get_db() as conn:
        try:
            cur = conn.execute("INSERT INTO categories (name, icon) VALUES (?, ?)", (name, icon))
            cat_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="分类已存在")
    log_action(user, "新增分类", detail=f"{icon} {name}")
    return {"ok": True, "id": cat_id}


@router.delete("/api/categories/{cat_id}")
async def del_category(cat_id: int, user: dict = Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="分类不存在")
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    log_action(user, "删除分类", detail=row["name"])
    return {"ok": True}
