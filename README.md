# 🏔️ 旅伴 — 中国旅游推荐问答系统

基于 **LangChain + 通义千问** 的智能旅游推荐问答系统。用户可通过浏览器进行旅游咨询，系统基于景点、住宿、美食知识库提供带来源引用的 AI 回答。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🗺️ **旅游问答推荐** | 基于知识库的 RAG 问答，推荐景点、住宿、美食 |
| 📖 **知识库引用** | 回答中标注 `[^N]` 格式引用，可查看知识库原文 |
| 🔐 **多用户管理** | 注册/登录，JWT 认证，独立会话隔离 |
| 💬 **多会话管理** | 每用户可创建多个独立旅游咨询会话 |
| 📝 **历史记录** | 对话持久化保存，不同时间登录可找回历史会话 |
| 🛠️ **知识库管理** | 管理员通过浏览器管理景点/住宿/美食知识库 |
| 📍 **地图导航** | 高德地图嵌入聊天框，标记推荐地点，路线规划 |
| 📋 **AI 行程规划** | 输入天数/预算/偏好，生成每日行程安排 |
| ⭐ **收藏系统** | 收藏感兴趣的景点/住宿/美食，生成出行清单 |
| 👍 **答案反馈** | 对 AI 回答进行评分，持续优化知识库质量 |

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn |
| **ORM** | SQLAlchemy 2.0 (async) |
| **数据库** | SQLite (开发) / PostgreSQL 16 (生产) |
| **向量数据库** | ChromaDB |
| **大模型** | 通义千问 (DashScope) |
| **AI 框架** | LangChain |
| **前端** | 原生 HTML/CSS/JS |
| **地图** | 高德地图 JS API 2.0 |
| **缓存** | Redis 7 |
| **部署** | Docker Compose |

## 🚀 快速启动

### 方式一：直接运行（开发环境）

```bash
# 1. 克隆项目
cd tourism-qa-system

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（复制 .env.example 为 .env 并填写 API Key）
cp .env.example backend/.env

# 4. 导入知识库数据
python scripts/import_knowledge.py

# 5. 启动后端
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 6. 打开浏览器访问
# 前端页面: 打开 frontend/index.html
# API 文档: http://localhost:8000/api/docs
```

### 方式二：Docker Compose（生产环境）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入真实的 API Key

# 2. 一键启动
docker compose up -d

# 3. 导入知识库
docker compose exec backend python /app/scripts/import_knowledge.py

# 4. 访问
# 前端: http://localhost:8080
# API:  http://localhost:8000/api/docs
```

### 方式三：Windows 一键启动

```bash
# 双击 run.bat 或在终端中运行
run.bat
```

## 📝 默认账号

| 角色 | 用户名 | 密码 | 权限 |
|------|--------|------|------|
| 管理员 | admin | 123456 | 知识库管理 + 问答 |
| 普通用户 | 自行注册 | — | 问答推荐 |

## 📡 API 接口

### 认证模块 `/api/auth`
- `POST /api/auth/register` — 用户注册
- `POST /api/auth/login` — 用户登录
- `PUT /api/auth/password` — 修改密码
- `GET /api/auth/me` — 获取当前用户信息

### 会话模块 `/api/conversations`
- `GET /api/conversations` — 会话列表
- `POST /api/conversations` — 创建会话
- `GET /api/conversations/{id}` — 会话详情 + 消息历史
- `DELETE /api/conversations/{id}` — 删除会话

### 问答模块 `/api/chat`
- `POST /api/chat/stream` — SSE 流式问答（核心接口）

### 知识库管理 `/api/admin`（管理员专用）
- `GET/POST /api/admin/attractions` — 景点列表/新增
- `GET/PUT/DELETE /api/admin/attractions/{id}` — 景点详情/更新/删除
- 同理：`/api/admin/hotels`、`/api/admin/foods`

### 地图模块 `/api/map`
- `GET /api/map/search` — POI 搜索
- `GET /api/map/route` — 路线规划

## 📂 项目结构

```
tourism-qa-system/
├── backend/                     # Python 后端
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库引擎
│   │   ├── models/              # SQLAlchemy 数据模型
│   │   ├── schemas/             # Pydantic 请求/响应
│   │   ├── api/                 # API 路由
│   │   │   ├── auth.py          # 认证
│   │   │   ├── chat.py          # SSE 流式问答
│   │   │   ├── conversation.py  # 会话管理
│   │   │   └── knowledge.py     # 知识库 CRUD
│   │   ├── core/                # 安全模块 + RAG 管线
│   │   └── services/            # 业务逻辑
│   └── Dockerfile
├── frontend/                    # 前端
│   ├── index.html               # 登录/注册
│   ├── pages/
│   │   ├── chat.html            # 问答主页面
│   │   └── admin-knowledge.html # 知识库管理
│   ├── css/                     # 样式
│   └── js/                      # 前端逻辑
├── data/                        # 种子数据（景点/住宿/美食 JSON）
├── scripts/                     # 运维脚本
├── docker-compose.yml           # Docker 部署
└── README.md
```

## 🔧 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 通义千问 API Key | `sk-ws-xxx` |
| `AMAP_API_KEY` | 高德地图 Key | `84673d0933xxx` |
| `JWT_SECRET` | JWT 签名密钥 | `your-random-secret` |
| `DATABASE_URL` | 数据库连接 | `sqlite+aiosqlite:///./tourism.db` |
| `REDIS_URL` | Redis 连接 | `redis://localhost:6379/0` |
