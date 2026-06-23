# 🏠 Home Stash

一个轻量级的家庭耗材库存管理系统，专为 NAS 用户设计。支持多用户、操作留痕、微信提醒、Docker 一键部署。

## 📖 项目背景

家里常用的耗材（纸巾、洗护用品、厨房调料等）总是用完了才发现没有了。超市买回来的东西往柜子里一放，时间一长就忘了还剩多少。

Home Stash 就是为了解决这个问题：一个跑在 NAS 上的库存管理工具，手机扫码就能记录消耗，库存不足自动提醒，再也不会临时发现洗发水用完了。

## ✨ 功能特性

- 📦 **6 大预设分类** — 婴儿/卫浴/厨房/日用/食品/医药，支持自定义分类
- 📊 **实时库存看板** — 低库存红色高亮，一目了然
- 🛒 **购物清单** — 一键从低库存添加，出门采购不漏项
- 📝 **采购记录** — 自动归档，支持消费统计
- 👥 **多用户体系** — 管理员 + 普通用户，操作全程留痕
- 📨 **微信推送** — 每天定时检查低库存，自动推送提醒
- 📧 **邮件通知** — SMTP 邮件低库存提醒，支持手动触发
- 💾 **自动备份** — 每天定时备份数据库，保留最近 7 天
- 🔒 **密码安全** — 密码 SHA-256 哈希存储，自动升级旧版明文
- 📱 **响应式设计** — 手机/PC/平板都能用
- 🐳 **Docker 部署** — 一键启动，数据独立持久化

## 🚀 快速开始

### Docker Compose（推荐）

```bash
git clone https://github.com/SpringShaw/home-stash.git
cd home-stash
docker compose up -d --build
```

访问 `http://localhost:8081`

### 裸机 Linux 部署

无需 Docker，直接在 Linux 上运行：

```bash
git clone https://github.com/SpringShaw/home-stash.git
cd home-stash

# 安装依赖
pip install fastapi==0.115.0 "uvicorn[standard]==0.32.0" python-multipart==0.0.12 pydantic==2.9.0 bcrypt==4.2.1

# 配置账号（首次运行前）
export ADMIN_ID=admin
export ADMIN_NAME=管理员
export ADMIN_PASSWORD=your_password

# 启动服务
bash app/start.sh
```

数据默认存储在项目目录下的 `data/`、`logs/`、`backups/`，可通过环境变量自定义：

```bash
export DATA_DIR=/opt/home-stash/data
export LOG_DIR=/opt/home-stash/logs
export BACKUP_DIR=/opt/home-stash/backups
```

### 首次登录

首次部署时，需要在 `docker-compose.yml` 中配置管理员和普通用户的账号信息：

```yaml
environment:
  - ADMIN_ID=你的管理员ID
  - ADMIN_NAME=管理员昵称
  - ADMIN_PASSWORD=管理员密码
  - USER_ID=普通用户ID
  - USER_NAME=用户昵称
  - USER_PASSWORD=用户密码
```

配置完成后启动服务，系统会自动创建账号。

## ⚙️ 配置说明

在 `docker-compose.yml` 中配置环境变量：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| DATA_DIR | ./data | 数据库存储目录 |
| LOG_DIR | ./logs | 日志存储目录 |
| BACKUP_DIR | ./backups | 备份存储目录 |
| ADMIN_ID | (空) | 管理员账号ID |
| ADMIN_NAME | 管理员 | 管理员昵称 |
| ADMIN_PASSWORD | admin123 | 管理员密码 |
| USER_ID | (空) | 普通用户账号ID |
| USER_NAME | 用户 | 普通用户昵称 |
| USER_PASSWORD | user123 | 普通用户密码 |
| WECHAT_TARGET | (空) | 微信推送目标ID |
| WECHAT_ACCOUNT | (空) | OpenClaw 微信账号ID |
| OPENCLAW_GATEWAY | http://127.0.0.1:33970 | OpenClaw Gateway 地址（Docker 中需设为 http://host.docker.internal:33970） |
| NOTIFY_HOUR | 20 | 提醒时间（小时） |
| NOTIFY_MINUTE | 0 | 提醒时间（分钟） |
| TRUSTED_IPS | (空) | IP白名单（逗号分隔） |
| TRUSTED_USER | (空) | 白名单默认登录用户ID |
| BACKUP_HOUR | 3 | 自动备份时间（小时） |
| BACKUP_MINUTE | 0 | 自动备份时间（分钟） |
| COOKIE_SECURE | false | Cookie 是否仅 HTTPS 传输（生产环境建议设为 true） |
| CORS_ORIGINS | * | CORS 允许来源（逗号分隔，如 https://yourdomain.com） |

### 微信推送配置

要启用微信低库存提醒，需要：

1. 部署 OpenClaw Gateway
2. 配置微信机器人
3. 在 `docker-compose.yml` 中填入 `WECHAT_TARGET` 和 `WECHAT_ACCOUNT`

## 📁 项目结构

```
home-stash/
├── app/
│   ├── main.py              # FastAPI 入口（挂载路由 + 启动）
│   ├── database.py          # 数据库连接、初始化、迁移
│   ├── auth.py              # 认证：密码哈希、会话、依赖注入
│   ├── models.py            # Pydantic 数据模型
│   ├── notifications.py     # 通知服务（微信 + 邮件）
│   ├── scheduler.py         # 定时任务（低库存微信推送）
│   ├── backup.py            # 自动备份（每天备份 SQLite，保留 7 天）
│   ├── start.sh             # 启动脚本（web + 定时任务 + 备份）
│   ├── routes/
│   │   ├── auth.py          # 认证路由（登录/登出）
│   │   ├── admin.py         # 管理员路由（设置/账号）
│   │   ├── categories.py    # 分类路由
│   │   ├── items.py         # 耗材路由（CRUD + 库存变动）
│   │   ├── shopping.py      # 购物清单路由
│   │   ├── purchases.py     # 采购记录 + 统计路由
│   │   ├── logs.py          # 操作日志路由
│   │   └── notify.py        # 通知路由
│   └── static/              # 前端静态文件（Vue3 + TailwindCSS）
│       ├── index.html       # 主页面
│       ├── login.html       # 登录页面
│       └── lib/             # 前端依赖库
├── docker-compose.yml
├── Dockerfile
└── deploy.sh
```

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/login | 用户登录 |
| GET | /api/categories | 获取分类列表 |
| POST | /api/categories | 添加分类 |
| GET | /api/items | 获取耗材列表 |
| POST | /api/items | 添加耗材 |
| PUT | /api/items/{id} | 更新耗材 |
| DELETE | /api/items/{id} | 删除耗材 |
| POST | /api/items/{id}/stock | 更新库存 |
| GET | /api/shopping-list | 获取购物清单 |
| GET | /api/stats | 消费统计 |
| GET | /api/health | 健康检查 |

## 🔧 常用维护命令

```bash
# 查看容器状态
docker ps | grep home-stash

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 查看实时日志
docker logs -f home-stash

# 备份数据库
cp data/stash.db backups/stash_$(date +%Y%m%d).db
```

## 📸 截图

> TODO: 添加截图

## 📄 License

MIT
