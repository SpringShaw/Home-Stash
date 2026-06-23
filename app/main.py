#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
家庭耗材库存管理系统 - Home Stash
主应用入口：初始化数据库、挂载路由、启动服务
"""

import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from database import STATIC_DIR, DB_PATH, init_db

# ============= FastAPI 应用 =============
app = FastAPI(title="Home Stash 家庭耗材库存")

# CORS 配置（可通过环境变量自定义允许的来源）
cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    print(f"🚀 Home Stash 已启动，数据库: {DB_PATH}")


# 静态文件
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ===== 页面路由 =====
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return FileResponse(str(STATIC_DIR / "login.html"))


# ===== 健康检查 =====
@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


# ===== 注册路由 =====
from routes.auth import router as auth_router
from routes.admin import router as admin_router
from routes.categories import router as categories_router
from routes.items import router as items_router
from routes.shopping import router as shopping_router
from routes.purchases import router as purchases_router
from routes.logs import router as logs_router
from routes.notify import router as notify_router

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(categories_router)
app.include_router(items_router)
app.include_router(shopping_router)
app.include_router(purchases_router)
app.include_router(logs_router)
app.include_router(notify_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
