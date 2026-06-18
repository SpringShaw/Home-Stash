FROM python:3.11-slim

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -sf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    python-multipart==0.0.12 \
    pydantic==2.9.0

# 复制应用代码
COPY app/ /app/

# 修改权限
RUN chmod +x /app/start.sh

# 创建数据卷目录
RUN mkdir -p /app/data /app/logs

EXPOSE 8000

# 健康检查（用Python自带的urllib，不依赖wget）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=5)" || exit 1

CMD ["/app/start.sh"]
