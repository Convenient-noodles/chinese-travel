# CLAUDE.md — 旅伴 (Tourism QA System) 项目指令

## 项目概述

**旅伴** — 基于 LangChain + 通义千问的中国旅游推荐问答系统。

- **前端**：Vanilla HTML/CSS/JS（SPA，无框架）
- **后端**：Python/FastAPI + SQLAlchemy 2.0 async
- **数据库**：SQLite（开发）/ PostgreSQL（部署）
- **AI**：通义千问 (DashScope) + RAG 检索增强
- **地图**：高德地图 JS API 2.0
- **搜索引擎**：DuckDuckGo (ddgs) 作为知识库回退

## 项目结构

```
tourism-qa-system/
├── backend/
│   ├── main.py              # FastAPI 入口 + StaticFiles 挂载
│   ├── config.py             # 环境变量配置
│   ├── database.py           # SQLAlchemy async engine
│   └── app/
│       ├── api/              # 路由层
│       │   ├── auth.py       # 注册/登录/刷新 Token
│       │   ├── chat.py       # SSE 流式问答
│       │   ├── conversation.py # 会话管理
│       │   ├── knowledge.py  # 知识库 CRUD + 批量导入
│       │   └── deps.py       # 认证依赖注入
│       ├── models/           # SQLAlchemy ORM
│       │   ├── user.py
│       │   ├── conversation.py
│       │   ├── message.py
│       │   └── knowledge.py
│       ├── schemas/          # Pydantic 请求/响应模型
│       └── services/
│           └── rag_service.py # RAG 检索 + LLM 流式生成
├── frontend/
│   ├── pages/
│   │   ├── chat.html         # 主问答页面
│   │   └── admin-knowledge.html # 知识库管理
│   ├── js/
│   │   ├── config.js, api.js, utils.js
│   │   ├── chat.js           # SSE 聊天逻辑
│   │   ├── map.js            # 高德地图 MapView 对象
│   │   ├── markdown.js       # marked.js 配置 + renderMarkdown()
│   │   └── admin-knowledge.js # 管理页 CRUD
│   └── css/
│       ├── common.css, chat.css, map.css, admin.css
├── .claude/                  # Claude Code 配置
│   ├── agents/               # 3 个 Agent
│   ├── skills/               # 4 个 Skill
│   ├── pass/                 # 门禁检查结果
│   └── settings.json         # 权限 + Hook
└── CLAUDE.md                 # 本文件
```

## 开发约定

### 后端 (Python/FastAPI)
- **所有 API 端点使用 async**（`async def`）
- **数据库查询使用 SQLAlchemy 2.0 async** + 参数绑定
- **SSE 流式使用 `StreamingResponse`** + `async generator`
- **JWT 认证**：access_token 30min, refresh_token 7d
- **配置从 `.env` 读取**，通过 `app.config.settings` 访问
- **启动命令**：`cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

### 前端 (Vanilla JS)
- **无框架**，所有状态用全局对象管理（`ChatState`, `MapView`）
- **SSE 接收用 `fetch` + `ReadableStream`**（不用 EventSource）
- **Markdown 渲染**：`renderMarkdown(text)` → `innerHTML`
- **地图组件**：`MapView` 对象（惰性初始化，按需展开面板）
- **API 请求**：统一通过 `API.get/post/put/delete` 发起

### 知识库管理
- **文件导入**：前端 `importFile()` → `POST /api/admin/knowledge/batch-import`
- **格式要求**：`=== 景点：名称 ===` / `=== 住宿：名称 ===` / `=== 美食：名称 ===`
- **字段提取**：城市、描述、经纬度、价格、最佳季节等

## 自定义技能索引

| 技能/Agent | 触发方式 | 功能 |
|-----------|---------|------|
| `/unit-test` | 命令行或 Skill | Python/JS 单元测试生成与执行 |
| `/comments-check` | 命令行或 Skill | 注释质量三维度检查 |
| `/security-audit` | 命令行或 Skill | 六维度安全审计 |
| `tester` agent | "门禁检查" | 自动执行全部测试 |
| `quality-engineer` agent | "门禁检查" | 自动审计变更文件 |
| `gitcommit-agent` | "提交代码" | 门禁编排 → 提交推送 |

## 环境变量 (.env)

```
DATABASE_URL=sqlite+aiosqlite:///./tourism.db
DASHSCOPE_API_KEY=sk-xxx
AMAP_API_KEY=xxx
JWT_SECRET=xxx
DEBUG=True
```
