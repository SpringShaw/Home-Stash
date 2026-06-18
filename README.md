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
| ADMIN_ID | (空) | 管理员账号ID |
| ADMIN_NAME | 管理员 | 管理员昵称 |
| ADMIN_PASSWORD | admin123 | 管理员密码 |
| USER_ID | (空) | 普通用户账号ID |
| USER_NAME | 用户 | 普通用户昵称 |
| USER_PASSWORD | user123 | 普通用户密码 |
| WECHAT_TARGET | (空) | 微信推送目标ID |
| WECHAT_ACCOUNT | (空) | OpenClaw 微信账号ID |
| OPENCLAW_GATEWAY | http://host.docker.internal:33970 | OpenClaw Gateway 地址 |
| NOTIFY_HOUR | 20 | 提醒时间（小时） |
| NOTIFY_MINUTE | 0 | 提醒时间（分钟） |
| TRUSTED_IPS | (空) | IP白名单（逗号分隔） |
| TRUSTED_USER | (空) | 白名单默认登录用户ID |

### 微信推送配置

要启用微信低库存提醒，需要：

1. 部署 OpenClaw Gateway
2. 配置微信机器人
3. 在 `docker-compose.yml` 中填入 `WECHAT_TARGET` 和 `WECHAT_ACCOUNT`

## 📁 项目结构

```
home-stash/
├── app/
│   ├── main.py          # FastAPI 主应用（单文件后端）
│   ├── scheduler.py     # 定时任务（低库存微信推送）
│   ├── start.sh         # 启动脚本（同时启动 web + 定时任务）
│   └── static/          # 前端静态文件（Vue3 + TailwindCSS）
│       ├── index.html   # 主页面
│       ├── login.html   # 登录页面
│       └── lib/         # 前端依赖库
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
