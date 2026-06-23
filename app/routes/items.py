#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""耗材路由：CRUD + 库存变动"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Form

from auth import require_login, require_admin
from database import get_db
from models import StockChange
from logs import log_action

router = APIRouter(tags=["耗材"])


@router.get("/api/items")
async def list_items(
    category_id: Optional[int] = None,
    low_only: bool = False,
    user: dict = Depends(require_login),
):
    with get_db() as conn:
        sql = """SELECT i.*, c.name as category_name, c.icon as category_icon
                 FROM items i LEFT JOIN categories c ON i.category_id = c.id WHERE 1=1"""
        params = []
        if category_id:
            sql += " AND i.category_id = ?"
            params.append(category_id)
        if low_only:
            sql += " AND i.stock < i.min_stock"
        sql += " ORDER BY (i.stock < i.min_stock) DESC, c.sort_order, i.name"
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.post("/api/items")
async def add_item(
    name: str = Form(..., max_length=100),
    category_id: int = Form(...),
    unit: str = Form("个", max_length=20),
    stock: float = Form(0, ge=0),
    min_stock: float = Form(1, ge=0),
    price: float = Form(0, ge=0),
    important: int = Form(0, ge=0, le=1),
    note: str = Form("", max_length=500),
    user: dict = Depends(require_login),
):
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO items (category_id, name, unit, stock, min_stock, price, important, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (category_id, name, unit, stock, min_stock, price, important, note),
        )
        item_id = cur.lastrowid
    log_action(user, "新增耗材", item_id=item_id, item_name=name,
               detail=f"初始库存{stock}{unit}, 阈值{min_stock}")
    return {"ok": True, "id": item_id}


@router.put("/api/items/{item_id}")
async def update_item(
    item_id: int,
    name: str = Form(..., max_length=100),
    unit: str = Form("个", max_length=20),
    min_stock: float = Form(1, ge=0),
    price: float = Form(0, ge=0),
    important: int = Form(0, ge=0, le=1),
    note: str = Form("", max_length=500),
    user: dict = Depends(require_login),
):
    with get_db() as conn:
        old = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="耗材不存在")
        conn.execute(
            """UPDATE items SET name=?, unit=?, min_stock=?, price=?,
               important=?, note=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (name, unit, min_stock, price, important, note, item_id),
        )
    log_action(user, "修改耗材", item_id=item_id, item_name=name,
               old_value=f"阈值{old['min_stock']}", new_value=f"阈值{min_stock}")
    return {"ok": True}


@router.delete("/api/items/{item_id}")
async def del_item(item_id: int, user: dict = Depends(require_admin)):
    with get_db() as conn:
        old = conn.execute("SELECT name FROM items WHERE id=?", (item_id,)).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="耗材不存在")
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    log_action(user, "删除耗材", item_id=item_id, item_name=old["name"])
    return {"ok": True}


@router.post("/api/items/{item_id}/change")
async def change_stock(item_id: int, data: StockChange, user: dict = Depends(require_login)):
    with get_db() as conn:
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="耗材不存在")
        old_stock = item["stock"]
        new_stock = max(0, old_stock + data.delta)
        conn.execute(
            "UPDATE items SET stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_stock, item_id),
        )
        if data.is_purchase and data.delta > 0:
            conn.execute(
                """INSERT INTO purchases (item_id, quantity, price, user_id, user_name, note)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (item_id, data.delta, data.price, user["id"], user["name"], data.note),
            )
    action = "采购入库" if data.is_purchase else ("增加库存" if data.delta > 0 else "减少库存")
    log_action(user, action, item_id=item_id, item_name=item["name"],
               old_value=f"{old_stock}{item['unit']}", new_value=f"{new_stock}{item['unit']}",
               detail=data.note)
    return {"ok": True, "new_stock": new_stock}
