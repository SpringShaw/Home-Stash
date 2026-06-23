#!/usr/bin/env python3
"""定时任务：每天检查低库存并推送微信"""
import os
import sqlite3
import time
from datetime import datetime

from database import DB_PATH

NOTIFY_HOUR = int(os.getenv("NOTIFY_HOUR", "20"))
NOTIFY_MINUTE = int(os.getenv("NOTIFY_MINUTE", "0"))


def check_low_stock():
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT i.name, i.stock, i.min_stock, i.unit, c.name as cat_name, c.icon
        FROM items i LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.stock < i.min_stock ORDER BY (i.stock / NULLIF(i.min_stock, 0))
    """).fetchall()
    conn.close()
    if not rows:
        print(f"[scheduler] {datetime.now()} 无低库存，跳过推送")
        return

    # 构造消息
    lines = [f"🏠 家庭耗材库存提醒（{datetime.now().strftime('%m-%d %H:%M')}）", ""]
    lines.append(f"⚠️ {len(rows)} 件耗材库存不足：\n")
    for r in rows:
        marker = "🔴" if r["stock"] <= 0 else "🟡"
        lines.append(f"{marker} {r['icon']} {r['name']}: {r['stock']}/{r['min_stock']}{r['unit']}")
    msg = "\n".join(lines)

    # 通过 notifications 模块发送
    try:
        from notifications import send_wechat
        if send_wechat(msg):
            print(f"[scheduler] {datetime.now()} 已推送 {len(rows)} 条低库存提醒")
        else:
            print(f"[scheduler] {datetime.now()} 微信推送未配置或失败")
    except Exception as e:
        print(f"[scheduler] 推送异常: {e}")


def main():
    print(f"[scheduler] 启动定时任务，每天 {NOTIFY_HOUR:02d}:{NOTIFY_MINUTE:02d} 检查低库存")
    last_run_day = None
    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if now.hour == NOTIFY_HOUR and now.minute == NOTIFY_MINUTE and last_run_day != today:
            try:
                check_low_stock()
                last_run_day = today
            except Exception as e:
                print(f"[scheduler] 任务执行失败: {e}")
        time.sleep(50)


if __name__ == "__main__":
    main()
