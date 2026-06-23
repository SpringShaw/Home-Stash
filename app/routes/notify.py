#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通知路由：手动触发低库存提醒"""

from fastapi import APIRouter, Depends

from auth import require_admin
from database import get_db
from notifications import send_email, build_low_stock_email

router = APIRouter(tags=["通知"])


@router.post("/api/notify/check")
async def check_and_notify(user: dict = Depends(require_admin)):
    """手动触发低库存检查并推送邮件提醒"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT i.name, i.stock, i.min_stock, i.unit, c.name as cat_name, c.icon
            FROM items i LEFT JOIN categories c ON i.category_id = c.id
            WHERE i.stock < i.min_stock ORDER BY (i.stock / i.min_stock)
        """).fetchall()
    if not rows:
        return {"ok": True, "low_count": 0, "sent": False}

    subject, body_html = build_low_stock_email(rows)
    sent = send_email(subject, body_html)
    return {"ok": True, "low_count": len(rows), "sent": sent}
