---
name: unit-test
description: 对 Python/FastAPI 后端和 JS 前端代码自动编写单元测试、执行测试、生成报告。
trigger: /unit-test
---

# 单元测试技能

你是一名测试工程师。用户请求对代码编写并执行单元测试时，按以下流程操作。

---

## 技术栈

| 层级 | 语言 | 测试框架 | 配置文件 |
|------|------|----------|----------|
| 后端 | Python 3.11+ / FastAPI | **pytest** + httpx + pytest-asyncio | `backend/pyproject.toml` 或 `backend/pytest.ini` |
| 前端 | Vanilla JavaScript | **Jest** | `jest.config.js` |

---

## 阶段一：分析输入

用户可能提供：
- **文件路径**：如 `backend/app/services/rag_service.py`、`frontend/js/chat.js`
- **函数名**：如 `_search_sqlite_sync`、`addMessage`
- **目录路径**：如 `backend/app/api/`（对目录下所有可测函数生成测试）
- **无参数**（当前打开的编辑器文件）：读取用户 IDE 当前选中的文件作为测试目标

### 第一步：读取目标代码

用 Read 工具读取目标文件，分析：
1. 项目类型（Python 后端 / JS 前端）
2. 导出方式（`def` / `async def` / `function` / `class`）
3. 所有可测试的函数/方法清单
4. 函数参数、返回值类型、外部依赖

### 第二步：确认测试范围

如果用户未指定具体函数，列出文件中所有函数让用户确认：

```
📋 检测到以下可测试函数：
  Python — backend/app/services/rag_service.py:
    1. _search_web(query, top_k) → 联网搜索
    2. _search_knowledge(query, top_k) → 知识库检索
    3. _search_sqlite(query, top_k) → SQLite 搜索
    4. _extract_snippet(content, query, max_len) → 片段提取
    5. _build_context(kb_results, query) → 上下文构建
    6. _extract_map_pois(kb_results) → 地图 POI 提取
    7. astream_chat(message, ...) → 流式聊天

请问要对哪些函数生成测试？（输入 "全部" 或函数名/编号）
```

---

## 阶段二：选择测试框架与安装

### Python 后端 — pytest

检查项目是否已有 pytest 配置。如果没有：

```bash
cd backend && pip install pytest pytest-asyncio httpx -q
```

创建 `backend/pytest.ini`：
```ini
[pytest]
testpaths = tests
python_files = test_*.py
asyncio_mode = auto
```

### JavaScript 前端 — Jest

检查项目是否已有 Jest 配置。如果没有：

```bash
npm install --save-dev jest
```

---

## 阶段三：编写测试代码

### 原则

1. **覆盖核心逻辑** — 正常输入、边界值、异常输入、空值/None/undefined
2. **Mock 外部依赖** — DashScope API、高德地图、DuckDuckGo、数据库
3. **每个测试用例只测一件事** — 一个 `test_` 对应一个断言场景
4. **描述清晰** — 测试名称用中文描述预期行为
5. **遵循项目风格** — 缩进、命名、注释风格与目标文件一致

### Python 测试模板

```python
"""
backend/app/services/rag_service.py — 单元测试
覆盖函数：_search_web, _extract_snippet, _extract_map_pois
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.rag_service import RAGService


class TestSearchWeb:
    """_search_web — 联网搜索"""

    def test_正常搜索返回结果(self):
        service = RAGService()
        with patch('app.services.rag_service.DDGS') as mock_ddgs:
            mock_instance = MagicMock()
            mock_instance.text.return_value = [
                {"title": "测试结果", "href": "http://example.com", "body": "内容"}
            ]
            mock_ddgs.return_value.__enter__.return_value = mock_instance

            results = service._search_web("杭州西湖", top_k=3)
            assert len(results) > 0
            assert results[0]["title"] == "测试结果"

    def test_搜索异常返回空列表(self):
        service = RAGService()
        with patch('app.services.rag_service.DDGS', side_effect=Exception("网络错误")):
            results = service._search_web("测试")
            assert results == []


class TestExtractSnippet:
    """_extract_snippet — 片段提取"""

    def test_短内容原样返回(self):
        service = RAGService()
        result = service._extract_snippet("短内容", "")
        assert result == "短内容"

    def test_长内容截取匹配位置(self):
        service = RAGService()
        content = "A" * 500 + "西湖" + "B" * 500
        result = service._extract_snippet(content, "西湖", max_len=300)
        assert "西湖" in result
        assert len(result) <= 350  # max_len + "..." overhead


class TestExtractMapPois:
    """_extract_map_pois — 地图 POI 提取"""

    def test_有坐标的数据被提取(self):
        service = RAGService()
        kb_results = [
            {"title": "西湖", "longitude": 120.14, "latitude": 30.24,
             "type": "attraction", "content": "杭州西湖", "tags": ""},
            {"title": "无坐标景点", "longitude": None, "latitude": None,
             "type": "attraction", "content": "", "tags": ""},
        ]
        pois = service._extract_map_pois(kb_results)
        assert len(pois) == 1
        assert pois[0]["name"] == "西湖"

    def test_空列表返回空(self):
        service = RAGService()
        assert service._extract_map_pois([]) == []
```

### FastAPI 异步端点测试模板

```python
"""
backend/app/api/chat.py — API 端点测试
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def test_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_chat_stream_需要认证(test_client):
    response = await test_client.post("/api/chat/stream",
        json={"message": "测试", "options": {}})
    assert response.status_code == 401  # 未登录


@pytest.mark.asyncio
async def test_健康检查(test_client):
    response = await test_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

### JavaScript 测试模板

```javascript
/**
 * frontend/js/chat.js — 单元测试
 * 覆盖函数：addMessage, renderConversationList
 */

// Mock DOM
document.body.innerHTML = `
  <div id="chatMessages"></div>
  <div id="conversationList"></div>
  <div id="conversationTitle"></div>
`;

// Mock 依赖
global.Utils = {
  escapeHtml: jest.fn(s => s),
  formatDate: jest.fn(() => '2026-01-01'),
  scrollToBottom: jest.fn(),
  truncate: jest.fn((s, n) => s),
};
global.renderMarkdown = jest.fn(s => s);
global.CONFIG = { API_BASE: 'http://localhost:8000' };
global.API = { getToken: jest.fn(() => 'test-token') };
global.ChatState = { currentConversationId: null, userLocation: null };

// 加载被测模块（需要先定义全局变量）
const chat = require('../js/chat.js');

describe('addMessage', () => {
  test('添加用户消息：正确设置 class', () => {
    const el = addMessage('user', '你好');
    expect(el.className).toContain('user');
    const content = el.querySelector('.message-content');
    expect(content.textContent).toBe('你好');
  });

  test('添加 AI 流式消息：内容为空', () => {
    const el = addMessage('assistant', '', true);
    expect(el.className).toContain('assistant');
    const bubble = el.querySelector('.message-bubble');
    expect(bubble.className).toContain('streaming-cursor');
  });
});
```

---

## 阶段四：配置测试运行器

### Python — pytest 配置

`backend/pytest.ini`：
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

### JavaScript — Jest 配置

`jest.config.js`：
```javascript
module.exports = {
  testEnvironment: 'jsdom',
  testMatch: ['**/__tests__/**/*.test.js', '**/*.test.js'],
  collectCoverageFrom: [
    'frontend/js/**/*.js',
    '!**/node_modules/**',
    '!**/__tests__/**',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'text-summary', 'html'],
};
```

---

## 阶段五：执行测试

```bash
# Python 后端
cd backend && python -m pytest tests/ -v

# Python 指定文件
cd backend && python -m pytest tests/test_rag_service.py -v

# Python 覆盖率
cd backend && python -m pytest tests/ --cov=app --cov-report=term-missing

# JavaScript 前端
npx jest

# JavaScript 指定文件
npx jest frontend/js/__tests__/chat.test.js
```

---

## 阶段六：生成测试报告

```markdown
# 🧪 单元测试报告

**目标文件**：`backend/app/services/rag_service.py`
**测试文件**：`backend/tests/test_rag_service.py`
**执行时间**：2026-07-06 17:30
**框架**：pytest 8.x

---

## 📊 测试结果

| 状态 | 数量 |
|------|------|
| ✅ 通过 | 24 |
| ❌ 失败 | 0 |
| 📝 总计 | 24 |
| ⏱️ 耗时 | 2.1s |

## 📈 覆盖率

| 指标 | 百分比 |
|------|--------|
| 语句覆盖率 | 91.2% |
| 分支覆盖率 | 85.7% |
| 函数覆盖率 | 100% |

## 📋 测试用例清单

### _search_knowledge
- ✅ 正常搜索返回结果
- ✅ 空关键词返回空列表
- ✅ SQLite 搜索异常返回空列表

### _extract_snippet
- ✅ 短内容原样返回
- ✅ 长内容截取匹配位置
- ✅ 无匹配关键词取开头
```

---

## 阶段七：清理与收尾

1. 如果安装了新的 pip/npm 依赖，提醒用户提交 `requirements.txt` / `package.json`
2. 建议将 `coverage/`、`.pytest_cache/` 加入 `.gitignore`
3. 询问用户是否需要将测试配置提交到 git

---

## 快速参考

| 场景 | 命令 |
|------|------|
| 后端全部测试 | `cd backend && python -m pytest tests/ -v` |
| 后端单个文件 | `cd backend && python -m pytest tests/test_rag_service.py -v` |
| 后端覆盖率 | `cd backend && python -m pytest tests/ --cov=app --cov-report=term-missing` |
| 前端测试 | `npx jest` |
| 前端单个文件 | `npx jest path/to/file.test.js` |
