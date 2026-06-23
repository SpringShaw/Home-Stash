#!/bin/sh
# 启动脚本：同时启动 web 服务、定时任务和自动备份
# 兼容 Docker 容器和裸机 Linux 部署

# 自动检测应用目录（Docker 中为 /app，裸机为脚本所在目录）
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
cd "$APP_DIR"

echo "📁 应用目录: $APP_DIR"
echo "📂 数据目录: ${DATA_DIR:-$APP_DIR/../data}"
echo "📋 日志目录: ${LOG_DIR:-$APP_DIR/../logs}"

# 启动定时任务（后台）
python "$APP_DIR/scheduler.py" &

# 启动自动备份（后台）
python "$APP_DIR/backup.py" &

# 启动主应用（前台）
exec uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir "$APP_DIR"
