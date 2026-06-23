#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理员路由：设置管理、账号管理"""

import traceback
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request

from auth import require_admin
from database import get_db, get_setting, set_setting, get_all_settings, get_all_accounts
from routes.logs import log_action

router = APIRouter(prefix="/api/admin", tags=["管理员"])

def _debug(msg):
    print(f"[DEBUG {datetime.now().isoformat()}] {msg}", flush=True)


# ===== 系统设置 =====
@router.get("/settings")
async def admin_get_settings(user: dict = Depends(require_admin)):
    return get_all_settings()


@router.post("/settings")
async def admin_save_settings(request: Request, user: dict = Depends(require_admin)):
    data = await request.json()
    allowed_keys = {
        "smtp_server", "smtp_port", "smtp_from", "smtp_auth_code", "smtp_to",
        "notify_hour", "notify_minute",
    }
    updated = 0
    for k, v in data.items():
        if k in allowed_keys:
            set_setting(k, str(v))
            updated += 1
    log_action(user, "修改系统设置", detail=f"更新了 {updated} 项设置")
    return {"ok": True}


# ===== 账号管理 =====
@router.get("/accounts")
async def admin_list_accounts(user: dict = Depends(require_admin)):
    return get_all_accounts()


@router.post("/accounts")
async def admin_add_or_update_account(request: Request, user: dict = Depends(require_admin)):
    _debug(f"=== /api/admin/accounts 请求开始, user={user} ===")
    try:
        from auth import hash_password

        raw_body = await request.body()
        _debug(f"请求体(raw): {raw_body.decode('utf-8', errors='replace')}")

        data = await request.json()
        _debug(f"请求体(JSON): {data}")

        aid = data.get("id", "").strip()[:50]
        name = data.get("name", "").strip()[:100]
        password = data.get("password", "").strip()[:128]
        role = data.get("role", "user")
        bound_ips = data.get("bound_ips", "").strip()[:500]

        _debug(f"解析后: aid='{aid}' name='{name}' password='{password}' role='{role}' bound_ips='{bound_ips}'")

        if not aid or not name:
            _debug("校验失败: aid或name为空")
            raise HTTPException(status_code=400, detail="账号和用户名不能为空")
        if role not in ("admin", "user"):
            _debug(f"校验失败: role={role} 无效")
            raise HTTPException(status_code=400, detail="无效的角色，只允许 admin 或 user")

        _debug("开始数据库操作...")
        with get_db() as conn:
            existing = conn.execute("SELECT id FROM accounts WHERE id=?", (aid,)).fetchone()
            _debug(f"账号是否存在: {existing is not None}")
            if existing:
                if password:
                    _debug(f"更新账号(含密码): {aid}")
                    conn.execute(
                        "UPDATE accounts SET name=?, password=?, role=?, bound_ips=? WHERE id=?",
                        (name, hash_password(password), role, bound_ips, aid),
                    )
                else:
                    _debug(f"更新账号(不含密码): {aid}")
                    conn.execute(
                        "UPDATE accounts SET name=?, role=?, bound_ips=? WHERE id=?",
                        (name, role, bound_ips, aid),
                    )
                _debug("写入log_action...")
                log_action(user, "修改账号", detail=f"{aid} {name} ({role}) bound_ips={bound_ips}")
            else:
                if not password:
                    _debug("新增账号失败: 密码为空")
                    raise HTTPException(status_code=400, detail="新增账号必须设置密码")
                _debug(f"新增账号: {aid}")
                conn.execute(
                    "INSERT INTO accounts (id, name, password, role, bound_ips) VALUES (?, ?, ?, ?, ?)",
                    (aid, name, hash_password(password), role, bound_ips),
                )
                _debug("写入log_action...")
                log_action(user, "新增账号", detail=f"{aid} {name} ({role})")
        _debug("数据库操作完成，返回 ok")
    except HTTPException:
        raise
    except Exception as e:
        _debug(f"!!! 异常: {type(e).__name__}: {e}")
        _debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {type(e).__name__}: {e}")
    return {"ok": True}


@router.delete("/accounts/{aid}")
async def admin_delete_account(aid: str, user: dict = Depends(require_admin)):
    if aid == user["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    with get_db() as conn:
        existing = conn.execute("SELECT name FROM accounts WHERE id=?", (aid,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="账号不存在")
        conn.execute("DELETE FROM accounts WHERE id=?", (aid,))
    log_action(user, "删除账号", detail=f"{aid} {existing['name']}")
    return {"ok": True}


@router.get("/visitor-ip")
async def admin_visitor_ip(request: Request, user: dict = Depends(require_admin)):
    client_ip = request.client.host if request.client else ""
    return {"ip": client_ip}
