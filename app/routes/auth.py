#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认证路由：登录/登出/IP 检测（含速率限制）"""

import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request, Form, Cookie
from fastapi.responses import JSONResponse

from auth import (
    get_user, require_login, create_session, delete_session,
    verify_password, upgrade_password, is_trusted_ip, COOKIE_SECURE,
)
from database import get_account
from routes.logs import log_action

router = APIRouter(tags=["认证"])

# ============= 登录速率限制 =============
_login_attempts: dict = {}  # {ip: [(timestamp, account), ...]}
LOGIN_RATE_WINDOW = 300     # 5 分钟窗口
LOGIN_RATE_LIMIT = 10       # 窗口内最多尝试次数


def _check_rate_limit(client_ip: str):
    """检查 IP 登录频率，超限则拒绝"""
    now = time.time()
    cutoff = now - LOGIN_RATE_WINDOW
    # 清理过期记录
    attempts = _login_attempts.get(client_ip, [])
    attempts = [(t, a) for t, a in attempts if t > cutoff]
    _login_attempts[client_ip] = attempts
    if len(attempts) >= LOGIN_RATE_LIMIT:
        raise HTTPException(status_code=429, detail=f"登录尝试过于频繁，请 {LOGIN_RATE_WINDOW // 60} 分钟后再试")


def _record_attempt(client_ip: str, account: str):
    """记录一次登录尝试"""
    _login_attempts.setdefault(client_ip, []).append((time.time(), account))


# ============= 路由 =============
@router.post("/api/login")
async def api_login(request: Request, account: str = Form(...), password: str = Form(...)):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    acct = get_account(account)
    if not acct or not verify_password(password, acct["password"]):
        _record_attempt(client_ip, account)
        raise HTTPException(status_code=401, detail="账号或密码错误")

    # 旧版密码自动升级为 bcrypt
    if not acct["password"].startswith("$2"):
        upgrade_password(account, password)

    token = create_session(account)
    log_action({"id": acct["id"], "name": acct["name"]}, "登录")
    resp = JSONResponse({
        "ok": True,
        "user": {"id": acct["id"], "name": acct["name"], "role": acct["role"]},
    })
    resp.set_cookie(
        "stash_token", token,
        max_age=30 * 86400,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )
    return resp


@router.post("/api/logout")
async def api_logout(token: Optional[str] = Cookie(None, alias="stash_token")):
    if token:
        delete_session(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("stash_token")
    return resp


@router.get("/api/me")
async def api_me(user: dict = Depends(require_login)):
    return {"id": user["id"], "name": user["name"], "role": user["role"]}


@router.get("/api/trusted-check")
async def api_trusted_check(request: Request):
    """检测当前 IP 是否在白名单内（不泄露账号 ID）"""
    client_ip = request.client.host if request.client else ""
    matched_id = is_trusted_ip(client_ip)
    return {"trusted": bool(matched_id), "ip": client_ip}
