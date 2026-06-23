#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接、初始化与迁移
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# ============= 路径配置 =============
# 项目根目录（app/ 的上级），Docker 环境下通过 PROJECT_ROOT 环境变量覆盖
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", str(Path(__file__).parent.parent)))

DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
DB_PATH = DATA_DIR / "stash.db"

LOG_DIR = Path(os.getenv("LOG_DIR", str(PROJECT_ROOT / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
ACTION_LOG = LOG_DIR / "action.log"

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(PROJECT_ROOT / "backups")))

STATIC_DIR = Path(__file__).parent / "static"

# ============= 默认数据 =============
DEFAULT_CATEGORIES = [
    {"name": "婴儿用品", "icon": "🧴", "items": ["湿纸巾", "棉柔巾", "可心柔", "尿不湿", "婴儿洗衣液", "金纺"]},
    {"name": "卫浴用品", "icon": "🚿", "items": ["洗发水", "沐浴露", "护发素", "牙膏", "洁厕灵", "洗衣液"]},
    {"name": "厨房用品", "icon": "🍳", "items": ["生抽", "老抽", "盐", "糖", "料酒", "醋", "鸡精", "蚝油", "菜籽油"]},
    {"name": "日用品", "icon": "🏠", "items": ["抽纸", "卷纸", "垃圾袋", "保鲜膜", "电池", "灯泡"]},
    {"name": "食品饮料", "icon": "🍞", "items": ["大米", "面条", "饮用水", "零食"]},
    {"name": "医药健康", "icon": "💊", "items": ["创可贴", "感冒药", "维生素", "口罩", "消毒液"]},
]

EN_DEFAULT_CATEGORIES = [
    {"name": "Baby Care", "icon": "🧴", "items": ["Baby Wipes", "Cotton Wipes", "Facial Tissue", "Diapers", "Baby Laundry Detergent", "Fabric Softener"]},
    {"name": "Bathroom", "icon": "🚿", "items": ["Shampoo", "Body Wash", "Conditioner", "Toothpaste", "Toilet Cleaner", "Laundry Detergent"]},
    {"name": "Kitchen", "icon": "🍳", "items": ["Soy Sauce", "Dark Soy Sauce", "Salt", "Sugar", "Cooking Wine", "Vinegar", "Chicken Powder", "Oyster Sauce", "Vegetable Oil"]},
    {"name": "Household", "icon": "🏠", "items": ["Facial Tissue", "Toilet Paper", "Trash Bags", "Plastic Wrap", "Batteries", "Light Bulbs"]},
    {"name": "Food & Drinks", "icon": "🍞", "items": ["Rice", "Noodles", "Drinking Water", "Snacks"]},
    {"name": "Health", "icon": "💊", "items": ["Band-Aids", "Cold Medicine", "Vitamins", "Face Masks", "Hand Sanitizer"]},
]

# ============= 数据库连接 =============
@contextmanager
def get_db():
    """获取数据库连接，自动提交/回滚"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============= 辅助查询函数 =============
def get_account(user_id: str):
    """根据 ID 查询单个账号"""
    with get_db() as conn:
        return conn.execute("SELECT * FROM accounts WHERE id=?", (user_id,)).fetchone()


def get_setting(key: str, default: str = "") -> str:
    """查询单条设置值"""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    """更新或插入设置"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
            (key, value),
        )


def get_all_settings() -> dict:
    """获取所有设置"""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def get_all_accounts() -> list:
    """获取所有账号（不含密码）"""
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, role, bound_ips, created_at FROM accounts").fetchall()
    return [dict(r) for r in rows]


# ============= 表结构定义 =============
TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        icon TEXT DEFAULT '📦',
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        unit TEXT DEFAULT '个',
        stock REAL DEFAULT 0,
        min_stock REAL DEFAULT 1,
        price REAL DEFAULT 0,
        important INTEGER DEFAULT 0,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS action_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        user_name TEXT NOT NULL,
        action TEXT NOT NULL,
        item_id INTEGER,
        item_name TEXT,
        old_value TEXT,
        new_value TEXT,
        detail TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        price REAL DEFAULT 0,
        user_id TEXT NOT NULL,
        user_name TEXT NOT NULL,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS shopping_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        custom_name TEXT,
        quantity REAL DEFAULT 1,
        done INTEGER DEFAULT 0,
        user_id TEXT NOT NULL,
        user_name TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
    )""",
    """CREATE TABLE IF NOT EXISTS accounts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        bound_ips TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT '',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
]


# ============= 迁移 =============
def run_migrations(c):
    """执行数据库迁移，确保旧版本平滑升级"""
    # settings 表补充 updated_at 列
    try:
        c.execute("ALTER TABLE settings ADD COLUMN updated_at TEXT DEFAULT ''")
    except Exception:
        pass

    # shopping_list 表字段迁移（旧版 name → custom_name，is_done → done）
    cols = [r[1] for r in c.execute("PRAGMA table_info(shopping_list)").fetchall()]
    if "name" in cols and "custom_name" not in cols:
        c.execute("DROP TABLE IF EXISTS shopping_list_old")
        c.execute("ALTER TABLE shopping_list RENAME TO shopping_list_old")
        c.execute("""CREATE TABLE shopping_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            custom_name TEXT,
            quantity REAL DEFAULT 1,
            done INTEGER DEFAULT 0,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
        )""")
        old = [r[1] for r in c.execute("PRAGMA table_info(shopping_list_old)").fetchall()]
        # 白名单验证列名，防止注入
        name_field = "name" if "name" in old else "custom_name"
        done_field = "is_done" if "is_done" in old else "done"
        user_field = "username" if "username" in old else "user_name"
        assert name_field in ("name", "custom_name")
        assert done_field in ("is_done", "done")
        assert user_field in ("username", "user_name")
        c.execute(
            f"INSERT INTO shopping_list (id, item_id, custom_name, quantity, done, user_id, user_name, created_at) "
            f"SELECT id, item_id, [{name_field}], quantity, [{done_field}], user_id, [{user_field}], created_at "
            f"FROM shopping_list_old"
        )
        c.execute("DROP TABLE shopping_list_old")

    # accounts 表补充 bound_ips 列
    acct_cols = [r[1] for r in c.execute("PRAGMA table_info(accounts)").fetchall()]
    if "bound_ips" not in acct_cols:
        c.execute("ALTER TABLE accounts ADD COLUMN bound_ips TEXT DEFAULT ''")
        print("✅ 已迁移: accounts 表添加 bound_ips 字段")


# ============= 初始化 =============
def init_db():
    """创建表、执行迁移、初始化默认数据"""
    with get_db() as conn:
        c = conn.cursor()

        # 创建表
        for sql in TABLES_SQL:
            c.execute(sql)

        # 运行迁移
        run_migrations(c)

        # 初始化默认账号（仅首次，通过环境变量配置）
        c.execute("SELECT COUNT(*) as cnt FROM accounts")
        if c.fetchone()["cnt"] == 0:
            import secrets as _secrets
            from auth import hash_password
            admin_id = os.getenv("ADMIN_ID", "")
            admin_name = os.getenv("ADMIN_NAME", "管理员")
            admin_password = os.getenv("ADMIN_PASSWORD", "")
            user_id = os.getenv("USER_ID", "")
            user_name = os.getenv("USER_NAME", "用户")
            user_password = os.getenv("USER_PASSWORD", "")
            if admin_id:
                if not admin_password:
                    admin_password = _secrets.token_urlsafe(12)
                    print(f"⚠️  未设置 ADMIN_PASSWORD，已生成随机密码: {admin_password}")
                    print(f"   请务必保存此密码，它不会再次显示！")
                c.execute(
                    "INSERT INTO accounts (id, name, password, role) VALUES (?, ?, ?, ?)",
                    (admin_id, admin_name, hash_password(admin_password), "admin"),
                )
            if user_id:
                if not user_password:
                    user_password = _secrets.token_urlsafe(12)
                    print(f"⚠️  未设置 USER_PASSWORD，已生成随机密码: {user_password}")
                    print(f"   请务必保存此密码，它不会再次显示！")
                c.execute(
                    "INSERT INTO accounts (id, name, password, role) VALUES (?, ?, ?, ?)",
                    (user_id, user_name, hash_password(user_password), "user"),
                )
            print("✅ 已初始化默认账号")

        # 初始化默认设置
        settings_defaults = [
            ("trusted_ips", os.getenv("TRUSTED_IPS", "")),
            ("trusted_user", os.getenv("TRUSTED_USER", "")),
            ("wechat_target", os.getenv("WECHAT_TARGET", "")),
            ("wechat_account", os.getenv("WECHAT_ACCOUNT", "")),
            ("openclaw_gateway", os.getenv("OPENCLAW_GATEWAY", "http://127.0.0.1:33970")),
            ("notify_hour", os.getenv("NOTIFY_HOUR", "20")),
            ("notify_minute", os.getenv("NOTIFY_MINUTE", "0")),
            ("smtp_server", ""),
            ("smtp_port", "465"),
            ("smtp_from", ""),
            ("smtp_auth_code", ""),
            ("smtp_to", ""),
        ]
        for key, val in settings_defaults:
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        print("✅ 系统设置已就绪")

        # 初始化默认分类和耗材（根据 APP_LANG 选择中/英文预设）
        c.execute("SELECT COUNT(*) as cnt FROM categories")
        if c.fetchone()["cnt"] == 0:
            app_lang = os.getenv("APP_LANG", "zh")
            cats = EN_DEFAULT_CATEGORIES if app_lang.startswith("en") else DEFAULT_CATEGORIES
            default_unit = "pc" if app_lang.startswith("en") else "个"
            for idx, cat in enumerate(cats):
                c.execute(
                    "INSERT INTO categories (name, icon, sort_order) VALUES (?, ?, ?)",
                    (cat["name"], cat["icon"], idx),
                )
                cat_id = c.lastrowid
                for item in cat["items"]:
                    c.execute(
                        "INSERT INTO items (category_id, name, unit, stock, min_stock) VALUES (?, ?, ?, ?, ?)",
                        (cat_id, item, default_unit, 0, 1),
                    )
            print(f"✅ 数据库已初始化，预设了 {len(cats)} 个分类")
