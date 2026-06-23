#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采购记录 + 消费统计路由"""

from fastapi import APIRouter, Depends

from auth import require_login
from database import get_db

router = APIRouter(tags=["采购记录"])


@router.get("/api/purchases")
async def list_purchases(days: int = 90, user: dict = Depends(require_login)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.*, i.name as item_name, i.unit, c.name as category_name
            FROM purchases p
            LEFT JOIN items i ON p.item_id = i.id
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE p.created_at >= datetime('now', ?, 'localtime')
            ORDER BY p.created_at DESC
        """, (f"-{days} days",)).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/stats")
async def get_stats(user: dict = Depends(require_login)):
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM items").fetchone()["c"]
        low = conn.execute("SELECT COUNT(*) as c FROM items WHERE stock < min_stock").fetchone()["c"]
        cats = conn.execute("SELECT COUNT(*) as c FROM categories").fetchone()["c"]
        month_spend = conn.execute("""
            SELECT COALESCE(SUM(price * quantity), 0) as total
            FROM purchases WHERE created_at >= datetime('now', 'start of month', 'localtime')
        """).fetchone()["total"]
        cat_spend = conn.execute("""
            SELECT c.name, c.icon, COALESCE(SUM(p.price * p.quantity), 0) as total
            FROM categories c
            LEFT JOIN items i ON i.category_id = c.id
            LEFT JOIN purchases p ON p.item_id = i.id
                AND p.created_at >= datetime('now', '-30 days', 'localtime')
            GROUP BY c.id ORDER BY total DESC LIMIT 6
        """).fetchall()
    return {
        "total_items": total,
        "low_stock_count": low,
        "category_count": cats,
        "month_spend": round(month_spend, 2),
        "category_spend": [dict(r) for r in cat_spend],
    }
