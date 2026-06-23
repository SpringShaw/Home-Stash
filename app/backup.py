#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库自动备份：每天定时备份 SQLite 数据库
保留最近 7 天的备份文件
"""

import os
import sqlite3
from datetime import datetime

from database import DB_PATH, BACKUP_DIR

BACKUP_HOUR = int(os.getenv("BACKUP_HOUR", "3"))   # 默认凌晨 3 点
BACKUP_MINUTE = int(os.getenv("BACKUP_MINUTE", "0"))
MAX_BACKUPS = 7  # 保留最近 7 天


def do_backup():
    """执行一次备份"""
    if not DB_PATH.exists():
        print("[backup] 数据库文件不存在，跳过备份")
        return False

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = BACKUP_DIR / f"stash_{timestamp}.db"

    try:
        # 使用 SQLite 在线备份 API，避免锁问题
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(str(backup_file))
        src.backup(dst)
        src.close()
        dst.close()
        print(f"[backup] ✅ 备份完成: {backup_file.name}")

        # 清理旧备份
        backups = sorted(BACKUP_DIR.glob("stash_*.db"), key=lambda f: f.stat().st_mtime, reverse=True)
        for old in backups[MAX_BACKUPS:]:
            old.unlink()
            print(f"[backup] 🗑️ 已清理旧备份: {old.name}")

        return True
    except Exception as e:
        print(f"[backup] ❌ 备份失败: {e}")
        if backup_file.exists() and backup_file.stat().st_size == 0:
            backup_file.unlink()
        return False


def main():
    """定时备份主循环"""
    import time
    print(f"[backup] 启动自动备份，每天 {BACKUP_HOUR:02d}:{BACKUP_MINUTE:02d} 执行，保留 {MAX_BACKUPS} 份")
    last_run_day = None
    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if now.hour == BACKUP_HOUR and now.minute == BACKUP_MINUTE and last_run_day != today:
            try:
                do_backup()
                last_run_day = today
            except Exception as e:
                print(f"[backup] 备份任务异常: {e}")
        time.sleep(50)


if __name__ == "__main__":
    main()
