---
name: security-audit
description: 代码安全审计 — 检查敏感信息泄露、注入漏洞、配置安全、XSS、加密缺陷等。适配 Python/FastAPI + Vanilla JS。
trigger: /security-audit
---

# 代码安全审计技能

你是一名安全审计工程师，负责审计 Python/FastAPI 后端和 Vanilla JS 前端代码。

---

## 技术栈安全关注点

| 层级 | 高风险区域 |
|------|-----------|
| Python/FastAPI | SQLAlchemy 注入、JWT 密钥泄露、`.env` 明文、`eval`/`pickle`、CORS 通配符 |
| JavaScript 前端 | `innerHTML` XSS、Token 存储、`location.href` 跳转、`localStorage` 敏感数据 |
| 配置文件 | `.env`、`settings.py`、高德地图 Key、DashScope API Key |

---

## 检查维度

| 维度 | 检查内容 | 严重程度 |
|------|----------|----------|
| **敏感信息泄露** | 密码、API Key、Token、数据库连接串硬编码 | 🔴 严重 |
| **注入漏洞** | SQL 拼接、XSS（innerHTML）、命令注入、路径遍历 | 🔴 严重 |
| **配置安全** | `.env` 明文敏感信息、CORS `*`、DEBUG 模式 | 🔴 严重 |
| **加密与认证** | 弱哈希、JWT 密钥强度、Token 过期策略 | 🟡 高风险 |
| **数据安全** | 日志泄露敏感信息、HTTP 明文、Session 安全 | 🟡 高风险 |
| **代码安全** | eval、pickle 反序列化、原型污染、SSRF | 🟡 高风险 |

---

## 阶段一：分析输入

用户可能提供：
- **文件路径**：如 `backend/app/api/chat.py`
- **目录路径**：如 `backend/`（递归检查）
- **无参数**：读取用户 IDE 当前选中的文件

### 第一步：读取目标代码

用 Read 工具读取目标文件，同时检查同目录下的配置文件（`.env`、`config.py`、`settings.py` 等）。

---

## 阶段二：逐维度检查

### 维度一：敏感信息泄露

**Python 检查规则**：

| 规则 | 危险模式 | 示例 |
|------|----------|------|
| 硬编码 API Key | `DASHSCOPE_API_KEY\s*=\s*['\"]sk-` | `DASHSCOPE_API_KEY = "sk-ws-H..."` |
| 数据库连接串 | `DATABASE_URL\s*=\s*sqlite.*` 含密码 | 无密码的 SQLite 可接受，但含密码的 MySQL/PostgreSQL 不可 |
| JWT Secret | `SECRET_KEY\s*=\s*['\"][^'\"]+['\"]` | `SECRET_KEY = "my-secret-123"` |
| 硬编码密码 | `password\s*=\s*['\"][^'\"]+['\"]` | `password = "123456"` |
| 内网地址暴露 | `192\.168\.\|10\.\d+\.` | 前端代码中的内网 API 地址 |
| 私钥/证书 | `-----BEGIN.*PRIVATE KEY-----` | PEM 格式密钥 |

**前端检查规则**：

| 规则 | 危险模式 |
|------|----------|
| Token 明文存储 | `localStorage.setItem\('token'` 无加密 |
| API Key 暴露 | 前端代码中出现 `sk-` 或 `api_key` |
| 高德 Key 暴露 | `AMAP_KEY\s*=\s*['\"]` 在前端（高德 JS Key 是公开的，但 Web Service Key 不能暴露） |

**输出格式**：
```
### 🔴 敏感信息泄露

❌ 高危 — backend/.env:3
   DASHSCOPE_API_KEY=sk-ws-H.RXXHLMX...
   问题：API Key 以明文存储
   建议：添加 .env 到 .gitignore，使用密钥管理服务

❌ 高危 — backend/app/config.py:12
   SECRET_KEY = "tourism-jwt-secret-key-2024"
   问题：JWT 密钥硬编码，且过于简单
   建议：使用环境变量 + 高强度随机字符串
```

### 维度二：注入漏洞

**Python — SQL 注入检查**：

| 危险模式 | 说明 |
|----------|------|
| `text(f"SELECT * FROM {table} WHERE ...")` | f-string 拼接 SQL |
| `conn.execute(f"SELECT ... WHERE name='{user_input}'")` | 字符串拼接 |
| `cursor.execute("SELECT ... WHERE id=" + str(user_id))` | 字符串拼接 |

**正确做法**：`text("SELECT ... WHERE name = :name")` + 参数绑定

**JavaScript — XSS 检查**：

| 危险模式 | 安全替代 |
|----------|----------|
| `element.innerHTML = userInput` | `element.textContent = userInput` |
| `document.write(userInput)` | 不使用 |
| `eval(userInput)` | 不使用 |
| `new Function(userInput)` | 不使用 |
| `location.href = userInput` | 校验 URL 白名单 |
| `setTimeout(string, 0)` | `setTimeout(function, 0)` |

**输出格式**：
```
### 🔴 注入漏洞

❌ 高危 — backend/app/services/rag_service.py:315
   sql = f"SELECT ... FROM {table} WHERE status='published' AND city = '{city}'"
   问题：f-string 拼接 SQL，存在注入风险（虽然 city 来自已知城市列表，建议仍用参数化）
   建议：统一使用 :param 参数绑定

❌ 高危 — frontend/js/chat.js:245
   contentEl.innerHTML = renderMarkdown(fullContent);
   问题：虽然 renderMarkdown 会转义，但需确认 marked.js 配置了 sanitize
   建议：确认 marked.js 安全配置，或使用 DOMPurify 预清理
```

### 维度三：配置文件安全

**检查目标文件**：
- `backend/.env`
- `backend/app/config.py` / `settings.py`
- `frontend/js/config.js`
- `.claude/settings.json`

**检查规则**：

| 检查项 | 危险模式 |
|--------|----------|
| 明文密钥 | `.env` 中的 `=sk-`、`=sk-` 模式 |
| DEBUG 模式 | `DEBUG=True`、`--reload` 在生产环境 |
| CORS 通配符 | `allow_origins=["*"]` |
| 无密码数据库 | `DATABASE_URL=sqlite:///...` 无认证（开发可接受） |
| 调试端点 | `/docs` 在生产暴露 |
| Token 过期过长 | `ACCESS_TOKEN_EXPIRE_MINUTES > 60` |

**输出格式**：
```
### 🔴 配置安全

❌ 高危 — backend/app/config.py:18
   DEBUG = True
   问题：生产环境开启 DEBUG 可能泄露堆栈信息和环境变量
   建议：从环境变量读取，默认 False

⚠️ 警告 — backend/main.py:42
   allow_origins=["*"]
   问题：CORS 允许所有来源
   建议：生产环境指定具体域名
```

### 维度四：加密与认证

**Python 检查**：

| 检查项 | 危险模式 |
|--------|----------|
| 弱密码哈希 | `hashlib.md5(password)`、`hashlib.sha1(password)` |
| JWT 弱密钥 | `SECRET_KEY` 长度 < 32 字符 |
| Token 无过期 | JWT 未设 `exp` |
| 不安全随机 | `random.random()` 用于安全场景 |
| 密码明文比较 | `password == stored_password` |

**检查 Passlib/BCrypt 使用是否规范**。

### 维度五：数据安全

| 检查项 | 说明 |
|--------|------|
| 日志泄露 | `print()` 打印 Token/密码/API Key |
| HTTP 明文 | 生产环境 `http://` 而非 `https://` |
| 敏感数据未脱敏 | 日志打印完整手机号/身份证 |
| 文件上传 | 未校验文件类型和大小 |
| SSE 流式 | 确认 SSE 响应头不含敏感缓存指令 |

### 维度六：代码安全

**Python 特定**：

| 检查项 | 危险模式 |
|--------|----------|
| unsafe eval | `eval()`、`exec()` |
| pickle 反序列化 | `pickle.loads(user_input)` |
| SSRF | `httpx.get(user_input)` 无 URL 校验 |
| 路径遍历 | `open(user_input_path)` 无校验 |
| 无超时 HTTP | `httpx.get(url)` 无 timeout 参数 |

---

## 阶段三：生成审计报告

```markdown
# 🔒 代码安全审计报告

**目标**：`backend/` + `frontend/`
**审计时间**：2026-07-06
**检查文件数**：12

---

## 📊 总览

| 维度 | 严重 | 高风险 | 警告 | 状态 |
|------|------|--------|------|------|
| 敏感信息泄露 | 2 | 0 | 1 | 🔴 |
| 注入漏洞 | 0 | 1 | 0 | 🟡 |
| 配置安全 | 1 | 0 | 2 | 🔴 |
| 加密与认证 | 0 | 0 | 1 | 🟢 |
| 数据安全 | 0 | 0 | 2 | 🟢 |
| 代码安全 | 0 | 0 | 1 | 🟢 |
| **合计** | **3** | **1** | **7** | |

## 🏷️ 综合评级：🔴 高风险 — 存在严重安全问题需立即修复

---

## 🔴 严重问题（P0 — 必须立即修复）

### 1. API Key 明文存储
- **文件**：`backend/.env:2`
- **问题**：`DASHSCOPE_API_KEY=sk-ws-H.RXXHLMX...`
- **修复**：确保 `.env` 在 `.gitignore` 中，使用 `.env.example` 模板

### 2. JWT Secret 强度不足
- **文件**：`backend/app/config.py:12`
- **问题**：密钥过于简单且硬编码
- **修复**：使用 `openssl rand -hex 32` 生成，从环境变量读取

### 3. CORS 配置过于宽松
- **文件**：`backend/main.py:42`
- **问题**：`allow_origins=["*"]`
- **修复**：生产环境限定具体域名

---

## 🔧 修复优先级

| 优先级 | 问题 | 建议耗时 |
|--------|------|----------|
| P0 | API Key 明文存储 | 5 分钟 |
| P0 | JWT Secret 强度 | 10 分钟 |
| P0 | CORS 通配符 | 5 分钟 |
| P1 | SQL 使用参数化查询 | 30 分钟 |
| P2 | 确保 marked.js 安全配置 | 15 分钟 |
```

---

## 阶段四：询问修复

```
🔒 审计报告已生成。

是否需要我逐个修复发现的安全问题？
- "修复 P0" — 先修复所有严重问题
- "全部修复" — 修复所有问题
- "跳过" — 仅保留报告
```

---

## 快速参考

| 命令 | 说明 |
|------|------|
| `/security-audit backend/` | 审计后端代码 |
| `/security-audit frontend/` | 审计前端代码 |
| `/security-audit` | 审计当前文件 |
