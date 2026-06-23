#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证：密码哈希、会话管理、依赖注入
"""

import hashlib
import json
import os
import secrets
import tempfile
import ipaddress
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import HTTPException, Depends, Request, Cookie

from database import get_db, get_account, get_setting, DATA_DIR

SESSION_FILE = DATA_DIR / "sessions.json"


# ============= 密码哈希（bcrypt） =============
def hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, stored_password: str) -> bool:
    """验证密码，兼容旧版 SHA-256 和明文，验证通过自动升级"""
    # 新版 bcrypt
    if stored_password.startswith("$2"):
        return bcrypt.checkpw(raw_password.encode("utf-8"), stored_password.encode("utf-8"))
    # 旧版 SHA-256（迁移期兼容）
    if stored_password.startswith("hashed:"):
        expected = "hashed:" + hashlib.sha256(raw_password.encode()).hexdigest()
        return secrets.compare_digest(stored_password, expected)
    # 最旧版明文（迁移期兼容）
    return secrets.compare_digest(raw_password, stored_password)


def upgrade_password(user_id: str, raw_password: str):
    """将旧版密码升级为 bcrypt 存储"""
    hashed = hash_password(raw_password)
    with get_db() as conn:
        conn.execute("UPDATE accounts SET password=? WHERE id=?", (hashed, user_id))
    print(f"✅ 已升级用户 {user_id} 的密码为 bcrypt 存储")


# ============= 会话管理（原子写入） =============
def load_sessions() -> dict:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_sessions(sessions: dict):
    """原子写入：先写临时文件再 rename，避免并发数据丢失"""
    fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False)
        os.replace(tmp_path, str(SESSION_FILE))
    except Exception:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


SESSIONS = load_sessions()


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "user_id": user_id,
        "created": datetime.now().isoformat(),
        "expires": (datetime.now() + timedelta(days=30)).isoformat(),
    }
    save_sessions(SESSIONS)
    return token


def delete_session(token: str):
    if token in SESSIONS:
        del SESSIONS[token]
        save_sessions(SESSIONS)


# ============= IP 白名单 =============
def is_trusted_ip(client_ip: str) -> str:
    """检查 IP 是否匹配账号绑定 IP，返回匹配的账号 ID"""
    if not client_ip:
        return ""
    try:
        req_ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return ""
    with get_db() as conn:
        rows = conn.execute("SELECT id, bound_ips FROM accounts WHERE bound_ips != ''").fetchall()
    # ① 检查账号级别的绑定 IP
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
    # ② 检查全局 IP 白名单（TRUSTED_IPS），命中则返回白名单默认用户
    trusted_ips = get_setting("trusted_ips", "")
    if trusted_ips:
        for entry in trusted_ips.split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                if req_ip in ipaddress.ip_network(entry, strict=False):
                    return get_setting("trusted_user", "")
            except ValueError:
                continue
    return ""


# ============= FastAPI 依赖注入 =============
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


def get_user(token: Optional[str] = Cookie(None, alias="stash_token")) -> Optional[dict]:
    """从 cookie 获取当前用户"""
    if not token or token not in SESSIONS:
        return None
    sess = SESSIONS[token]
    if datetime.fromisoformat(sess["expires"]) < datetime.now():
        delete_session(token)
        return None
    user_id = sess["user_id"]
    acct = get_account(user_id)
    if not acct:
        return None
    return {"id": acct["id"], "name": acct["name"], "role": acct["role"]}


def require_login(request: Request, user: Optional[dict] = Depends(get_user)) -> dict:
    """登录校验：优先 session，其次账号绑定 IP 免密"""
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
    """管理员权限校验"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
