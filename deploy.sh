#!/bin/bash
set -e

# 日志文件路径
LOG_FILE="./deploy_logs/$(date +%Y-%m-%d_%H-%M-%S).log"
mkdir -p ./deploy_logs

# 开始记录日志（同时输出到屏幕和文件）
exec > >(tee -a "$LOG_FILE") 2>&1

echo "🚀 开始部署 home-stash..."
echo "📝 日志文件：$LOG_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. 停止旧容器
echo "🛑 停止旧容器..."
docker compose down 2>/dev/null || true

# 2. 构建并启动（直接从工作区构建）
echo "🔨 构建并启动服务..."
docker compose up -d --build

# 3. 查看状态
echo "✅ 部署完成！容器状态："
docker ps --filter "name=home-stash" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🌐 访问地址：http://$(hostname -I | awk '{print $1}'):8081"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
