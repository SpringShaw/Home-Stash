#!/bin/sh
# 启动脚本：同时启动 web 服务和定时任务

# 启动定时任务（后台）
python /app/scheduler.py &

# 启动主应用（前台）
exec uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir /app
