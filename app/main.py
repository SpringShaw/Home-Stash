#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
家庭耗材库存管理系统 - Home Stash
单文件后端服务（FastAPI + SQLite）
"""

import os
import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional, List
from pathlib import Path

import ipaddress

from fastapi import FastAPI, HTTPException, Depends, Request, Response, Form, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ============= 配置 =============
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "stash.db"
SESSION_FILE = DATA_DIR / "sessions.json"

LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
ACTION_LOG = LOG_DIR / "action.log"

STATIC_DIR = Path(__file__).parent / "static"

# 默认分类和耗材
DEFAULT_CATEGORIES = [
    {"name": "婴儿用品", "icon": "🧴", "items": ["湿纸巾", "棉柔巾", "可心柔", "尿不湿", "婴儿洗衣液", "金纺"]},
    {"name": "卫浴用品", "icon": "🚿", "items": ["洗发水", "沐浴露", "护发素", "牙膏", "洁厕灵", "洗衣液"]},
    {"name": "厨房用品", "icon": "🍳", "items": ["生抽", "老抽", "盐", "糖", "料酒", "醋", "鸡精", "蚝油", "菜籽油"]},
    {"name": "日用品", "icon": "🏠", "items": ["抽纸", "卷纸", "垃圾袋", "保鲜膜", "电池", "灯泡"]},
    {"name": "食品饮料", "icon": "🍞", "items": ["大米", "面条", "饮用水", "零食"]},
    {"name": "医药健康", "icon": "💊", "items": ["创可贴", "感冒药", "维生素", "口罩", "消毒液"]},
]

# ============= 数据库 =============
@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """初始化数据库"""
    with get_db() as conn:
        c = conn.cursor()
        # 分类表
        c.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                icon TEXT DEFAULT '📦',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 耗材表
        c.execute("""
            CREATE TABLE IF NOT EXISTS items (
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
            )
        """)
        # 操作日志表
        c.execute("""
            CREATE TABLE IF NOT EXISTS action_logs (
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
            )
        """)
        # 采购记录表
        c.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                price REAL DEFAULT 0,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
            )
        """)
        # 购物清单表
        c.execute("""
            CREATE TABLE IF NOT EXISTS shopping_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                custom_name TEXT,
                quantity REAL DEFAULT 1,
                done INTEGER DEFAULT 0,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
            )
        """)
        # 账号表
        c.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                bound_ips TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 系统设置表
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 迁移：旧表的 settings 可能没有 updated_at 列
        try:
            c.execute("ALTER TABLE settings ADD COLUMN updated_at TEXT DEFAULT ''")
        except Exception:
            pass  # 列已存在则忽略

        # 检查并修复shopping_list表字段
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
            name_field = "name" if "name" in old else "custom_name"
            done_field = "is_done" if "is_done" in old else "done"
            user_field = "username" if "username" in old else "user_name"
            c.execute(f"INSERT INTO shopping_list (id, item_id, custom_name, quantity, done, user_id, user_name, created_at) SELECT id, item_id, {name_field}, quantity, {done_field}, user_id, {user_field}, created_at FROM shopping_list_old")
            c.execute("DROP TABLE shopping_list_old")

        # 迁移：为旧accounts表补充 bound_ips 字段
        acct_cols = [r[1] for r in c.execute("PRAGMA table_info(accounts)").fetchall()]
        if "bound_ips" not in acct_cols:
            c.execute("ALTER TABLE accounts ADD COLUMN bound_ips TEXT DEFAULT ''")
            print("✅ 已迁移: accounts 表添加 bound_ips 字段")

        # 初始化默认账号（仅首次，通过环境变量配置）
        c.execute("SELECT COUNT(*) as cnt FROM accounts")
        if c.fetchone()["cnt"] == 0:
            admin_id = os.getenv("ADMIN_ID", "")
            admin_name = os.getenv("ADMIN_NAME", "管理员")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
            user_id = os.getenv("USER_ID", "")
            user_name = os.getenv("USER_NAME", "用户")
            user_password = os.getenv("USER_PASSWORD", "user123")
            if admin_id:
                c.execute("INSERT INTO accounts (id, name, password, role) VALUES (?, ?, ?, ?)",
                          (admin_id, admin_name, admin_password, "admin"))
            if user_id:
                c.execute("INSERT INTO accounts (id, name, password, role) VALUES (?, ?, ?, ?)",
                          (user_id, user_name, user_password, "user"))
            print("✅ 已初始化默认账号")

        # 初始化默认设置（逐条，已有则跳过）
        settings_defaults = [
            ("trusted_ips", os.getenv("TRUSTED_IPS", "")),
            ("trusted_user", os.getenv("TRUSTED_USER", "")),
            ("wechat_target", os.getenv("WECHAT_TARGET", "")),
            ("wechat_account", os.getenv("WECHAT_ACCOUNT", "")),
            ("openclaw_gateway", os.getenv("OPENCLAW_GATEWAY", "http://host.docker.internal:33970")),
            ("notify_hour", os.getenv("NOTIFY_HOUR", "20")),
            ("notify_minute", os.getenv("NOTIFY_MINUTE", "0")),
            # 邮件SMTP配置
            ("smtp_server", ""),
            ("smtp_port", "465"),
            ("smtp_from", ""),
            ("smtp_auth_code", ""),
            ("smtp_to", ""),
        ]
        for key, val in settings_defaults:
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        print("✅ 系统设置已就绪")

        # 检查是否需要初始化默认数据
        c.execute("SELECT COUNT(*) as cnt FROM categories")
        if c.fetchone()["cnt"] == 0:
            for idx, cat in enumerate(DEFAULT_CATEGORIES):
                c.execute("INSERT INTO categories (name, icon, sort_order) VALUES (?, ?, ?)",
                          (cat["name"], cat["icon"], idx))
                cat_id = c.lastrowid
                for item in cat["items"]:
                    c.execute("""INSERT INTO items (category_id, name, unit, stock, min_stock)
                                 VALUES (?, ?, ?, ?, ?)""",
                              (cat_id, item, "个", 0, 1))
            print(f"✅ 数据库已初始化，预设了 {len(DEFAULT_CATEGORIES)} 个分类")


# ============= 设置与账号（从DB读取） =============
def get_setting(key: str, default: str = "") -> str:
    """从数据库读取设置"""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key: str, value: str):
    """写入设置到数据库"""
    with get_db() as conn:
        conn.execute("""INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(key) DO UPDATE SET value=?, updated_at=CURRENT_TIMESTAMP""",
                     (key, value, value))

def get_all_settings() -> dict:
    """读取所有设置"""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}

def get_account(user_id: str) -> Optional[dict]:
    """从数据库读取账号"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id=?", (user_id,)).fetchone()
    if not row:
        return None
    return {"id": row["id"], "name": row["name"], "password": row["password"], "role": row["role"], "bound_ips": row["bound_ips"]}

def get_all_accounts() -> list:
    """读取所有账号（不返回密码）"""
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, role, bound_ips, created_at FROM accounts ORDER BY role, id").fetchall()
    return [dict(r) for r in rows]

def is_trusted_ip(client_ip: str) -> str:
    """判断客户端IP是否匹配某账号绑定IP，匹配则返回该账号ID"""
    if not client_ip:
        return ""
    try:
        req_ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return ""
    with get_db() as conn:
        rows = conn.execute("SELECT id, bound_ips FROM accounts WHERE bound_ips != ''").fetchall()
    for r in rows:
        for entry in r["bound_ips"].split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                if req_ip in ipaddress.ip_network(entry, strict=False):
                    return r["id"]
            except ValueError:
                continue
    return ""
    return get_setting("trusted_user", "")


# ============= 会话管理 =============
def load_sessions():
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_sessions(sessions):
    SESSION_FILE.write_text(json.dumps(sessions, ensure_ascii=False), encoding="utf-8")

SESSIONS = load_sessions()

def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "user_id": user_id,
        "created": datetime.now().isoformat(),
        "expires": (datetime.now() + timedelta(days=30)).isoformat()
    }
    save_sessions(SESSIONS)
    return token

def get_user(token: Optional[str] = Cookie(None, alias="stash_token")) -> Optional[dict]:
    if not token or token not in SESSIONS:
        return None
    sess = SESSIONS[token]
    if datetime.fromisoformat(sess["expires"]) < datetime.now():
        del SESSIONS[token]
        save_sessions(SESSIONS)
        return None
    user_id = sess["user_id"]
    acct = get_account(user_id)
    if not acct:
        return None
    user = {"id": acct["id"], "name": acct["name"], "role": acct["role"]}
    return user

def require_login(request: Request, user: Optional[dict] = Depends(get_user)) -> dict:
    """登录校验：优先session，其次按账号绑定IP免密"""
    if user:
        return user
    client_ip = request.client.host if request.client else ""
    if client_ip:
        matched_uid = is_trusted_ip(client_ip)
        if matched_uid:
            acct = get_account(matched_uid)
            if acct:
                return {"id": acct["id"], "name": acct["name"], "role": acct["role"]}
    raise HTTPException(status_code=401, detail="未登录或登录已过期")

def require_admin(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user

# ============= 操作日志 =============
def log_action(user: dict, action: str, item_id: Optional[int] = None,
               item_name: str = "", old_value: str = "", new_value: str = "", detail: str = ""):
    with get_db() as conn:
        conn.execute("""INSERT INTO action_logs
                        (user_id, user_name, action, item_id, item_name, old_value, new_value, detail)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                     (user["id"], user["name"], action, item_id, item_name,
                      str(old_value), str(new_value), detail))
    line = f"[{datetime.now().isoformat()}] {user['name']}({user['id']}) {action} {item_name} {old_value}→{new_value} {detail}\n"
    try:
        with open(ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

# ============= 微信提醒 =============
def send_wechat_notify(message: str):
    """通过 OpenClaw 发微信通知"""
    target = get_setting("wechat_target", "")
    account_id = get_setting("wechat_account", "")
    if not target:
        return False
    try:
        import urllib.request
        gateway = get_setting("openclaw_gateway", "http://host.docker.internal:33970")
        payload = {
            "channel": "openclaw-weixin",
            "to": target,
            "message": message
        }
        if account_id:
            payload["accountId"] = account_id
        req = urllib.request.Request(
            f"{gateway}/api/message/send",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        print(f"微信提醒失败: {e}")
        return False

# ============= 邮件通知 =============
def send_email(subject: str, body_html: str) -> bool:
    """通过SMTP发送HTML邮件"""
    server = get_setting("smtp_server", "")
    port = get_setting("smtp_port", "465")
    from_addr = get_setting("smtp_from", "")
    auth_code = get_setting("smtp_auth_code", "")
    to_addr = get_setting("smtp_to", "")

    if not server or not from_addr or not auth_code or not to_addr:
        print("邮件配置不完整，跳过")
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body_html, "html", "utf-8")
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject

        if port == "465":
            with smtplib.SMTP_SSL(server, int(port), timeout=10) as smtp:
                smtp.login(from_addr, auth_code)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, int(port), timeout=10) as smtp:
                smtp.starttls()
                smtp.login(from_addr, auth_code)
                smtp.send_message(msg)
        print(f"✅ 邮件发送成功: {subject}")
        return True
    except Exception as e:
        print(f"邮件发送异常: {e}")
        return False

# ============= FastAPI 应用 =============
app = FastAPI(title="Home Stash 家庭耗材库存")

@app.on_event("startup")
async def startup():
    init_db()
    print(f"🚀 Home Stash 已启动，数据库: {DB_PATH}")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ===== 页面路由 =====
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return FileResponse(str(STATIC_DIR / "login.html"))

# ===== 认证接口 =====
@app.post("/api/login")
async def api_login(account: str = Form(...), password: str = Form(...)):
    acct = get_account(account)
    if not acct or acct["password"] != password:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_session(account)
    log_action({"id": acct["id"], "name": acct["name"]}, "登录")
    resp = JSONResponse({
        "ok": True,
        "user": {"id": acct["id"], "name": acct["name"], "role": acct["role"]}
    })
    resp.set_cookie("stash_token", token, max_age=30*86400, httponly=True, samesite="lax")
    return resp

@app.post("/api/logout")
async def api_logout(token: Optional[str] = Cookie(None, alias="stash_token")):
    if token and token in SESSIONS:
        del SESSIONS[token]
        save_sessions(SESSIONS)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("stash_token")
    return resp

@app.get("/api/me")
async def api_me(user: dict = Depends(require_login)):
    return {"id": user["id"], "name": user["name"], "role": user["role"]}

@app.get("/api/trusted-check")
async def api_trusted_check(request: Request):
    """检测当前IP是否在白名单内（用于登录页自动跳转）"""
    client_ip = request.client.host if request.client else ""
    matched_id = is_trusted_ip(client_ip)
    return {"trusted": bool(matched_id), "ip": client_ip, "matched_account": matched_id or ""}

# ===== 管理员接口 =====
@app.get("/api/admin/settings")
async def admin_get_settings(user: dict = Depends(require_admin)):
    """获取所有系统设置"""
    return get_all_settings()

@app.post("/api/admin/settings")
async def admin_save_settings(request: Request, user: dict = Depends(require_admin)):
    """批量更新系统设置"""
    data = await request.json()
    allowed_keys = {"smtp_server", "smtp_port", "smtp_from", "smtp_auth_code", "smtp_to",
                    "notify_hour", "notify_minute"}
    for k, v in data.items():
        if k in allowed_keys:
            set_setting(k, str(v))
    log_action(user, "修改系统设置", detail=f"更新了 {len(data)} 项设置")
    return {"ok": True}

@app.get("/api/admin/accounts")
async def admin_list_accounts(user: dict = Depends(require_admin)):
    """获取所有账号"""
    return get_all_accounts()

@app.post("/api/admin/accounts")
async def admin_add_or_update_account(request: Request, user: dict = Depends(require_admin)):
    """新增或更新账号"""
    data = await request.json()
    aid = data.get("id", "").strip()
    name = data.get("name", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "user")
    bound_ips = data.get("bound_ips", "").strip()

    if not aid or not name:
        raise HTTPException(status_code=400, detail="账号和用户名不能为空")

    with get_db() as conn:
        existing = conn.execute("SELECT id FROM accounts WHERE id=?", (aid,)).fetchone()
        if existing:
            if password:
                conn.execute("UPDATE accounts SET name=?, password=?, role=?, bound_ips=? WHERE id=?",
                             (name, password, role, bound_ips, aid))
            else:
                conn.execute("UPDATE accounts SET name=?, role=?, bound_ips=? WHERE id=?",
                             (name, role, bound_ips, aid))
            log_action(user, "修改账号", detail=f"{aid} {name} ({role}) bound_ips={bound_ips}")
        else:
            if not password:
                raise HTTPException(status_code=400, detail="新增账号必须设置密码")
            conn.execute("INSERT INTO accounts (id, name, password, role, bound_ips) VALUES (?, ?, ?, ?, ?)",
                         (aid, name, password, role, bound_ips))
            log_action(user, "新增账号", detail=f"{aid} {name} ({role})")
    return {"ok": True}

@app.delete("/api/admin/accounts/{aid}")
async def admin_delete_account(aid: str, user: dict = Depends(require_admin)):
    """删除账号"""
    if aid == user["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    with get_db() as conn:
        existing = conn.execute("SELECT name FROM accounts WHERE id=?", (aid,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="账号不存在")
        conn.execute("DELETE FROM accounts WHERE id=?", (aid,))
    log_action(user, "删除账号", detail=f"{aid} {existing['name']}")
    return {"ok": True}

@app.get("/api/admin/visitor-ip")
async def admin_visitor_ip(request: Request, user: dict = Depends(require_admin)):
    """获取当前访问者IP（用于白名单配置参考）"""
    client_ip = request.client.host if request.client else ""
    return {"ip": client_ip}

# ===== 分类接口 =====
@app.get("/api/categories")
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

@app.post("/api/categories")
async def add_category(name: str = Form(...), icon: str = Form("📦"),
                       user: dict = Depends(require_login)):
    with get_db() as conn:
        try:
            cur = conn.execute("INSERT INTO categories (name, icon) VALUES (?, ?)", (name, icon))
            cat_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="分类已存在")
    log_action(user, "新增分类", detail=f"{icon} {name}")
    return {"ok": True, "id": cat_id}

@app.delete("/api/categories/{cat_id}")
async def del_category(cat_id: int, user: dict = Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="分类不存在")
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    log_action(user, "删除分类", detail=row["name"])
    return {"ok": True}

# ===== 耗材接口 =====
@app.get("/api/items")
async def list_items(category_id: Optional[int] = None, low_only: bool = False,
                     user: dict = Depends(require_login)):
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

@app.post("/api/items")
async def add_item(name: str = Form(...), category_id: int = Form(...),
                   unit: str = Form("个"), stock: float = Form(0),
                   min_stock: float = Form(1), price: float = Form(0),
                   important: int = Form(0), note: str = Form(""),
                   user: dict = Depends(require_login)):
    with get_db() as conn:
        cur = conn.execute("""INSERT INTO items
                              (category_id, name, unit, stock, min_stock, price, important, note)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                           (category_id, name, unit, stock, min_stock, price, important, note))
        item_id = cur.lastrowid
    log_action(user, "新增耗材", item_id=item_id, item_name=name,
               detail=f"初始库存{stock}{unit}, 阈值{min_stock}")
    return {"ok": True, "id": item_id}

@app.put("/api/items/{item_id}")
async def update_item(item_id: int, name: str = Form(...), unit: str = Form("个"),
                      min_stock: float = Form(1), price: float = Form(0),
                      important: int = Form(0), note: str = Form(""),
                      user: dict = Depends(require_login)):
    with get_db() as conn:
        old = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="耗材不存在")
        conn.execute("""UPDATE items SET name=?, unit=?, min_stock=?, price=?,
                        important=?, note=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                     (name, unit, min_stock, price, important, note, item_id))
    log_action(user, "修改耗材", item_id=item_id, item_name=name,
               old_value=f"阈值{old['min_stock']}", new_value=f"阈值{min_stock}")
    return {"ok": True}

@app.delete("/api/items/{item_id}")
async def del_item(item_id: int, user: dict = Depends(require_admin)):
    with get_db() as conn:
        old = conn.execute("SELECT name FROM items WHERE id=?", (item_id,)).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="耗材不存在")
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    log_action(user, "删除耗材", item_id=item_id, item_name=old["name"])
    return {"ok": True}

# ===== 库存变动 =====
class StockChange(BaseModel):
    delta: float
    note: str = ""
    is_purchase: bool = False
    price: float = 0

@app.post("/api/items/{item_id}/change")
async def change_stock(item_id: int, data: StockChange, user: dict = Depends(require_login)):
    with get_db() as conn:
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="耗材不存在")
        old_stock = item["stock"]
        new_stock = max(0, old_stock + data.delta)
        conn.execute("UPDATE items SET stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (new_stock, item_id))
        if data.is_purchase and data.delta > 0:
            conn.execute("""INSERT INTO purchases
                            (item_id, quantity, price, user_id, user_name, note)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (item_id, data.delta, data.price, user["id"], user["name"], data.note))
    action = "采购入库" if data.is_purchase else ("增加库存" if data.delta > 0 else "减少库存")
    log_action(user, action, item_id=item_id, item_name=item["name"],
               old_value=f"{old_stock}{item['unit']}", new_value=f"{new_stock}{item['unit']}",
               detail=data.note)
    return {"ok": True, "new_stock": new_stock}

# ===== 采购记录 =====
@app.get("/api/purchases")
async def list_purchases(days: int = 90, user: dict = Depends(require_login)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.*, i.name as item_name, i.unit, c.name as category_name
            FROM purchases p
            LEFT JOIN items i ON p.item_id = i.id
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE p.created_at >= datetime('now', ?, 'localtime')
            ORDER BY p.created_at DESC
        """, (f'-{days} days',)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/stats")
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
        "category_spend": [dict(r) for r in cat_spend]
    }

# ===== 购物清单 =====
@app.get("/api/shopping")
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

@app.post("/api/shopping")
async def add_shopping(item_id: Optional[int] = Form(None),
                       custom_name: str = Form(""),
                       quantity: float = Form(1),
                       user: dict = Depends(require_login)):
    with get_db() as conn:
        cur = conn.execute("""INSERT INTO shopping_list
                              (item_id, custom_name, quantity, user_id, user_name)
                              VALUES (?, ?, ?, ?, ?)""",
                           (item_id, custom_name, quantity, user["id"], user["name"]))
    log_action(user, "加入购物清单", item_id=item_id, item_name=custom_name or f"item#{item_id}")
    return {"ok": True, "id": cur.lastrowid}

@app.put("/api/shopping/{sid}/done")
async def shopping_done(sid: int, user: dict = Depends(require_login)):
    with get_db() as conn:
        conn.execute("UPDATE shopping_list SET done=1 WHERE id=?", (sid,))
    return {"ok": True}

@app.delete("/api/shopping/{sid}")
async def del_shopping(sid: int, user: dict = Depends(require_login)):
    with get_db() as conn:
        conn.execute("DELETE FROM shopping_list WHERE id=?", (sid,))
    return {"ok": True}

# ===== 操作日志 =====
@app.get("/api/logs")
async def list_logs(limit: int = 100, user: dict = Depends(require_login)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM action_logs ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]

# ===== 低库存提醒 =====
@app.post("/api/notify/check")
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

    mail_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    mail_date_short = datetime.now().strftime("%y%m%d")

    # 构造低库存明细
    detail_lines = []
    for r in rows:
        marker = "🔴" if r["stock"] <= 0 else "🟡"
        detail_lines.append(f"{marker} {r['icon']} {r['cat_name']} | {r['name']}: {r['stock']}/{r['min_stock']}{r['unit']}")
    detail_str = "\n".join(detail_lines)

    # 构造HTML邮件（模板风格与参考脚本一致）
    subject = f"【Home Stash】耗材低库存提醒 | {mail_date_short}"
    body_html = f"""<pre style="font-family: Monaco, Consolas, monospace; font-size: 13px; line-height: 1.6;">
⚠️ 家庭耗材库存提醒
📊 有 {len(rows)} 件耗材库存不足
🕐 {mail_date}
=============================================================

📋 低库存清单
=============================================================
{detail_str}

=============================================================
👉 打开 Home Stash 管理库存
</pre>"""

    sent = send_email(subject, body_html)
    return {"ok": True, "low_count": len(rows), "sent": sent}

# ===== 健康检查 =====
@app.get("/api/health")
async def health():
    return {"status": "ok", "db": str(DB_PATH), "time": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
