"""
RAG 检索增强生成服务
- 知识库检索 + DuckDuckGo 联网搜索回退
- 使用通义千问 (DashScope) 进行流式生成
"""

import json
import re
import os
from ddgs import DDGS
from typing import AsyncGenerator, List, Dict, Any, Optional
from datetime import datetime

import dashscope
from dashscope import Generation
from http import HTTPStatus

from app.config import settings

# 配置 DashScope API Key
dashscope.api_key = settings.DASHSCOPE_API_KEY


# ============================================================
# System Prompt — 旅游推荐助手
# ============================================================

SYSTEM_PROMPT = """你是"旅伴"，一个专业的中国旅游推荐助手。你的知识涵盖中国旅游景点、酒店住宿、地方美食。

## 回答规则
1. 如果提供了【知识库资料】，回答必须基于资料内容，在对应句子末尾用 [^1]、[^2] 标注引用
2. 如果没有提供知识库资料，自由回答即可，不要编造引用标记
3. 回答风格：热情、专业、细致，像一位经验丰富的导游
4. 对于景点和住宿，提供位置信息（城市、地址），方便用户导航
5. 推荐时考虑季节因素和用户偏好

## Markdown 格式要求（重要）
- 使用 ## 作为大标题，### 作为子标题
- 景点/美食/住宿信息用 **粗体** 突出关键字段（如 **名称**、**城市**、**门票**）
- 多个推荐用数字列表或项目符号排列
- 实用信息（交通、注意事项）放在最后
- 每个推荐之间用 --- 分隔
- 最后写一句简短的祝福语

## 回答格式模板
### 🏔️ 景点名称
- **城市**：XX省XX市
- **特色**：简要描述核心亮点
- **门票**：XX元
- **最佳季节**：X月至X月
- **游玩建议**：1-2句实用建议

### 🍜 美食名称
- **地区**：XX市
- **口味**：描述风味特点
- **人均**：XX-XX元
- **推荐理由**：1句点睛

当前日期：{current_date}
"""


# ============================================================
# RAG Service
# ============================================================

class RAGService:
    """
    RAG 检索增强生成服务

    负责：
    1. 从 ChromaDB 检索相关知识
    2. 构建 Prompt
    3. 调用通义千问流式生成
    4. 提取引用和地图数据
    """

    def __init__(self):
        self._chroma_client = None
        self._collections = {}

    def _init_chroma(self):
        """惰性初始化 ChromaDB 客户端"""
        if self._chroma_client is not None:
            return

        try:
            import chromadb
            persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
            os.makedirs(persist_dir, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=persist_dir)
            # 获取或创建三个 collection
            for name in ["kb_attractions", "kb_hotels", "kb_foods"]:
                try:
                    self._collections[name] = self._chroma_client.get_collection(name)
                except Exception:
                    self._collections[name] = self._chroma_client.create_collection(
                        name=name,
                        metadata={"hnsw:space": "cosine"}
                    )
        except Exception as e:
            print(f"[RAG] ChromaDB 初始化失败: {e}，将使用无知识库模式")
            self._chroma_client = None
            self._collections = {}

    def _search_web(self, query: str, top_k: int = 5) -> List[Dict]:
        """DuckDuckGo 联网搜索"""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query + " 旅游", max_results=top_k))
            web_results = []
            for r in results:
                web_results.append({
                    "id": "web_" + str(hash(r.get("href", ""))),
                    "title": r.get("title", "未知"),
                    "type": "web",
                    "content": r.get("body", ""),
                    "score": 0.80,
                    "city": "",
                    "longitude": None,
                    "latitude": None,
                    "tags": "",
                    "source_url": r.get("href", ""),
                })
            return web_results
        except Exception as e:
            print(f"[Web Search] 搜索失败: {e}")
            return []

    def _search_knowledge(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        SQLite 关键词检索（主力）+ ChromaDB 向量检索（补充）
        返回: [{id, title, type, content, score, city, longitude, latitude, ...}]
        """
        # 主力：SQLite 关键词搜索（中文分词，精准匹配）
        sqlite_results = self._search_sqlite(query, top_k)

        # 补充：ChromaDB 向量检索（语义相似，与关键词结果合并去重）
        chroma_results = self._search_chromadb(query, top_k)
        sqlite_ids = {r["id"] for r in sqlite_results}
        for r in chroma_results:
            if r["id"] not in sqlite_ids:
                r["score"] = r["score"] * 0.6  # ChromaDB 结果降权
                sqlite_results.append(r)

        # 按分数排序
        sqlite_results.sort(key=lambda x: x["score"], reverse=True)
        return sqlite_results[:top_k]

    def _search_chromadb(self, query: str, top_k: int) -> List[Dict]:
        """ChromaDB 向量检索"""
        self._init_chroma()

        if not self._chroma_client:
            return []

        all_results = []
        for coll_name, kb_type in [
            ("kb_attractions", "attraction"),
            ("kb_hotels", "hotel"),
            ("kb_foods", "food"),
        ]:
            coll = self._collections.get(coll_name)
            if coll is None or coll.count() == 0:
                continue

            try:
                results = coll.query(
                    query_texts=[query],
                    n_results=min(top_k, coll.count()),
                    include=["documents", "metadatas", "distances"],
                )
                if results and results["ids"] and results["ids"][0]:
                    for i, doc_id in enumerate(results["ids"][0]):
                        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                        distance = results["distances"][0][i] if results["distances"] else 0
                        similarity = 1 - distance

                        all_results.append({
                            "id": doc_id,
                            "title": metadata.get("name", "未知"),
                            "type": kb_type,
                            "content": results["documents"][0][i] if results["documents"] else "",
                            "score": round(similarity, 4),
                            "city": metadata.get("city", ""),
                            "longitude": metadata.get("longitude"),
                            "latitude": metadata.get("latitude"),
                            "tags": metadata.get("tags", ""),
                        })
            except Exception as e:
                print(f"[RAG] ChromaDB 检索 {coll_name} 失败: {e}")

        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    def _search_sqlite(self, query: str, top_k: int) -> List[Dict]:
        """
        SQLite 关键词匹配回退方案
        通过 jieba 分词 + LIKE 匹配在 SQLite 中搜索知识库
        """
        import asyncio
        try:
            import jieba
        except ImportError:
            jieba = None

        # 提取关键词：使用 jieba 分词或简单字符匹配
        if jieba:
            keywords = list(jieba.cut(query))
        else:
            # 简单处理：按常见分隔符拆分
            import re
            keywords = [w for w in re.split(r'[，。？?！!、\s]+', query) if len(w) >= 2]

        # 如果没有有效关键词，返回空
        keywords = [k for k in keywords if len(k) >= 2]
        if not keywords:
            keywords = [query[:10]]  # 至少用查询前10个字符

        results = []
        try:
            return self._search_sqlite_sync(query, top_k, keywords)
        except Exception as e:
            print(f"[RAG] SQLite 搜索失败: {e}")
            return []

    # 中文停用词（旅游场景下无检索意义的通用词）
    _STOP_WORDS = {
        "我", "你", "他", "她", "它", "我们", "你们", "他们", "的", "了", "在", "是",
        "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到",
        "说", "要", "去", "会", "着", "没有", "看", "好", "自己", "这", "那", "哪",
        "什么", "怎么", "如何", "怎样", "为什么", "可以", "能", "能够", "应该",
        "帮", "帮我", "请", "请问", "想", "想要", "需要", "推荐", "介绍", "告诉",
        "一下", "一些", "哪里", "哪儿", "哪个", "位置", "定位", "地方", "位于",
        "有没有", "是否", "还是", "或者", "以及", "还有", "其他", "别的",
        "谢谢", "感谢", "你好", "您好", "麻烦", "知道", "了解", "查询", "搜索",
        "找", "找到", "给", "让", "把", "被", "从", "对", "向", "与", "跟",
        "吗", "呢", "吧", "啊", "哦", "嗯", "哈", "呀", "嘛",
    }

    # 意图关键词：用于判断用户想搜哪类知识库
    _INTENT_KEYWORDS = {
        "food": {"美食", "小吃", "火锅", "烤鸭", "餐厅", "饭店", "早餐", "夜宵",
                 "特产", "小吃街", "美食街", "好吃", "必吃", "口味", "味道",
                 "推荐菜", "特色菜", "名菜", "甜品", "点心", "吃什么"},
        "attraction": {"景点", "游玩", "旅游", "游览", "风景", "景区", "公园",
                       "古镇", "博物馆", "寺庙", "故居", "遗址", "园林",
                       "峡谷", "瀑布", "草原", "沙漠", "观光", "名胜", "打卡"},
        "hotel": {"住宿", "酒店", "宾馆", "民宿", "旅馆", "青旅", "度假村",
                  "入住", "房间", "客房", "过夜", "下榻", "预订", "套房"},
    }

    def _detect_intent(self, query: str, keywords: List[str]) -> set:
        """根据查询关键词检测搜索意图，返回需要搜索的表类型集合"""
        query_text = query + "".join(keywords)
        intents = set()
        for intent_type, intent_words in self._INTENT_KEYWORDS.items():
            if any(w in query_text for w in intent_words):
                intents.add(intent_type)
        return intents if intents else {"attraction", "hotel", "food"}

    def _search_sqlite_sync(self, query: str, top_k: int, keywords: List[str]) -> List[Dict]:
        """同步数据库搜索（支持 SQLite / MySQL / PostgreSQL）"""
        from sqlalchemy import create_engine, text

        # 过滤停用词，优先保留有意义的实体词
        meaningful_kw = [k for k in keywords if k not in self._STOP_WORDS and len(k) >= 2]
        if not meaningful_kw:
            meaningful_kw = keywords[:3]

        # 检测搜索意图，只搜相关类型的表
        intents = self._detect_intent(query, meaningful_kw)

        # 检测城市名，精确过滤（从数据库动态获取 + 常用城市补充）
        known_cities = {"北京", "上海", "杭州", "成都", "西安", "南京", "广州", "深圳",
                        "重庆", "武汉", "苏州", "桂林", "丽江", "拉萨", "昆明", "长沙",
                        "郑州", "青岛", "大连", "厦门", "三亚", "黄山", "张家界", "贵阳",
                        "哈尔滨", "沈阳", "天津", "宁波", "福州", "珠海", "东莞", "毕节",
                        # 山西省
                        "太原", "大同", "朔州", "忻州", "阳泉", "吕梁", "晋中", "长治",
                        "晋城", "临汾", "运城", "山西",
                        # 其他常用
                        "安顺", "遵义", "阿坝", "九寨沟", "南昌", "合肥", "南宁", "兰州",
                        "银川", "呼和浩特", "乌鲁木齐", "西宁", "海口", "济南", "石家庄",
                        "温州", "无锡", "常州", "扬州", "徐州", "洛阳", "开封", "宜昌",
                        "襄阳", "岳阳", "株洲", "九江", "景德镇", "秦皇岛", "威海", "烟台"}
        # 找出所有匹配的城市，优先选最长的（更具体），同长度选最后出现的
        # 中文习惯"山西临汾"→"临汾"在后更具体
        province_names = {"山西", "陕西", "浙江", "江苏", "广东", "广西", "云南", "贵州",
                         "四川", "湖南", "湖北", "河南", "河北", "山东", "福建", "江西",
                         "安徽", "辽宁", "吉林", "黑龙江", "甘肃", "青海", "海南", "台湾",
                         "内蒙古", "西藏", "宁夏", "新疆"}
        city_filter = None
        matched_cities = [kw for kw in meaningful_kw if kw in known_cities]
        if matched_cities:
            # 按长度降序，同长度非省份优先（城市比省份更具体）
            matched_cities.sort(key=lambda x: (len(x), 0 if x in province_names else 1), reverse=True)
            city_filter = matched_cities[0]

        all_models = [
            ("attractions", "attraction"),
            ("hotels", "hotel"),
            ("foods", "food"),
        ]
        models = [(t, k) for t, k in all_models if k in intents]

        # 将异步驱动 URL 转换为同步驱动 URL
        db_url = settings.DATABASE_URL
        if "+aiosqlite" in db_url:
            db_url = db_url.replace("+aiosqlite", "")
            connect_args = {"check_same_thread": False}
        elif "+aiomysql" in db_url:
            db_url = db_url.replace("+aiomysql", "+pymysql")
            connect_args = {"charset": "utf8mb4"}
        elif "+asyncpg" in db_url:
            db_url = db_url.replace("+asyncpg", "")
            connect_args = {}
        else:
            connect_args = {}

        sync_engine = create_engine(db_url, connect_args=connect_args)

        # 类别词映射到 item_type（这些词不会出现在知识库文本中）
        # 使用包含匹配：jieba 可能把"特色美食"合成一个词，需要检测子串
        _CATEGORY_PAIRS = [
            ("景点", "attraction"), ("景区", "attraction"), ("风景", "attraction"),
            ("游玩", "attraction"), ("旅游", "attraction"), ("名胜", "attraction"),
            ("古迹", "attraction"), ("打卡", "attraction"),
            ("美食", "food"), ("小吃", "food"), ("好吃", "food"), ("餐厅", "food"),
            ("饭店", "food"), ("料理", "food"), ("日料", "food"), ("面食", "food"),
            ("火锅", "food"), ("烤鸭", "food"), ("特产", "food"), ("甜品", "food"),
            ("住宿", "hotel"), ("酒店", "hotel"), ("宾馆", "hotel"), ("民宿", "hotel"),
            ("旅馆", "hotel"), ("青旅", "hotel"), ("度假", "hotel"),
        ]

        def _detect_category(kw: str) -> str | None:
            """检测关键词是否包含类别词（子串匹配）"""
            for cat_word, cat_type in _CATEGORY_PAIRS:
                if cat_word in kw:
                    return cat_type
            return None

        # 检测用户整体意图：如果查询中有类别词，所有搜索都加类型过滤
        overall_type_filter = None
        for kw in meaningful_kw:
            ct = _detect_category(kw)
            if ct:
                overall_type_filter = ct
                break  # 取第一个类别词作为全局过滤

        results = []
        seen_key = set()
        table = "knowledge_items"

        with sync_engine.connect() as conn:
            for kw in meaningful_kw[:5]:
                try:
                    # 检查当前关键词是否包含类别词（子串匹配）
                    category_type = _detect_category(kw)

                    # 构建 type 过滤条件（当前词类别 > 全局类别）
                    type_filter = category_type or overall_type_filter

                    if city_filter and type_filter:
                        # 有城市 + 类别：按城市和类型过滤
                        if category_type:
                            # 关键词本身就是类别词，不需要文本搜索
                            sql = (
                                f"SELECT id, name, item_type, city, content, longitude, latitude "
                                f"FROM {table} WHERE status='published' AND city LIKE :city_like "
                                f"AND item_type = :itype "
                                f"LIMIT :limit"
                            )
                            params = {"city_like": f"%{city_filter}%", "itype": type_filter, "limit": top_k}
                        else:
                            # 关键词是城市名等，需要文本搜索+类型过滤
                            sql = (
                                f"SELECT id, name, item_type, city, content, longitude, latitude "
                                f"FROM {table} WHERE status='published' AND city LIKE :city_like "
                                f"AND item_type = :itype "
                                f"AND (name LIKE :kw OR city LIKE :kw OR content LIKE :kw) "
                                f"LIMIT :limit"
                            )
                            params = {"city_like": f"%{city_filter}%", "itype": type_filter,
                                     "kw": f"%{kw}%", "limit": top_k}
                    elif city_filter:
                        sql = (
                            f"SELECT id, name, item_type, city, content, longitude, latitude "
                            f"FROM {table} WHERE status='published' AND city LIKE :city_like "
                            f"AND (name LIKE :kw OR city LIKE :kw OR content LIKE :kw) "
                            f"LIMIT :limit"
                        )
                        params = {"kw": f"%{kw}%", "limit": top_k, "city_like": f"%{city_filter}%"}
                    elif type_filter:
                        if category_type:
                            # 关键词本身就是类别词
                            sql = (
                                f"SELECT id, name, item_type, city, content, longitude, latitude "
                                f"FROM {table} WHERE status='published' "
                                f"AND item_type = :itype "
                                f"LIMIT :limit"
                            )
                            params = {"itype": type_filter, "limit": top_k}
                        else:
                            # 非类别关键词+类型过滤：文本搜索+类型
                            sql = (
                                f"SELECT id, name, item_type, city, content, longitude, latitude "
                                f"FROM {table} WHERE status='published' "
                                f"AND item_type = :itype "
                                f"AND (name LIKE :kw OR city LIKE :kw OR content LIKE :kw) "
                                f"LIMIT :limit"
                            )
                            params = {"itype": type_filter, "kw": f"%{kw}%", "limit": top_k}
                    else:
                        sql = (
                            f"SELECT id, name, item_type, city, content, longitude, latitude "
                            f"FROM {table} WHERE status='published' "
                            f"AND (name LIKE :kw OR city LIKE :kw OR content LIKE :kw) "
                            f"LIMIT :limit"
                        )
                        params = {"kw": f"%{kw}%", "limit": top_k}

                    rows = conn.execute(text(sql), params)
                    for row in rows:
                        item_key = str(row[0])
                        if item_key in seen_key:
                            continue
                        seen_key.add(item_key)

                        # row: id, name, item_type, city, content, longitude, latitude
                        name = row[1] or ""
                        item_type = row[2] or "attraction"
                        city_val = row[3] or ""
                        content = row[4] or ""
                        kw_lower = kw.lower()

                        # 打分：名称 > 城市 > 内容，长关键词权重更高
                        kw_weight = min(len(kw) / 4.0, 1.0)  # 4字以上满分
                        score = 0.0
                        if category_type:
                            # 类别词匹配：按类型匹配，有城市过滤更精准
                            if city_filter:
                                score = 0.50 + 0.10 * kw_weight  # 城市+类别: 0.50~0.60
                            else:
                                score = 0.40 + 0.10 * kw_weight  # 仅类别: 0.40~0.50
                        elif kw_lower in name.lower():
                            score = 0.50 + 0.30 * kw_weight  # 名称匹配 0.50~0.80
                        elif kw_lower in city_val.lower():
                            score = 0.45 + 0.20 * kw_weight  # 城市匹配 0.45~0.65
                        elif kw_lower in content.lower():
                            score = 0.10 + 0.25 * kw_weight  # 内容匹配 0.10~0.35
                        elif city_filter:
                            # 有城市过滤但关键词未匹配到具体字段：给城市匹配基础分
                            score = 0.35

                        if score > 0:
                            results.append({
                                "id": item_key,
                                "title": name,
                                "type": item_type,
                                "content": content,
                                "score": min(score, 0.95),
                                "city": city_val,
                                "longitude": row[5],
                                "latitude": row[6],
                                "tags": "",
                            })
                except Exception as e:
                    print(f"[RAG] 搜索失败: {e}")

        sync_engine.dispose()

        # 去重 + 高质量优先
        seen = set()
        unique_results = []
        for r in sorted(results, key=lambda x: x["score"], reverse=True):
            if r["id"] not in seen:
                seen.add(r["id"])
                unique_results.append(r)

        # 质量阈值：至少 0.35 分（含长关键词内容匹配），丢弃极低分噪音
        good_results = [r for r in unique_results if r["score"] >= 0.35]
        if good_results:
            return good_results[:top_k]
        return unique_results[:top_k]

    def _extract_snippet(self, content: str, query: str, max_len: int = 300) -> str:
        """从内容中提取与查询最相关的片段"""
        if len(content) <= max_len:
            return content
        # 找到最能匹配查询的位置
        best_pos = 0
        for kw in query:
            pos = content.lower().find(kw.lower())
            if pos >= 0:
                best_pos = pos
                break
        # 取匹配位置前后各 max_len/2 字符
        start = max(0, best_pos - max_len // 2)
        end = min(len(content), start + max_len)
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        return snippet

    def _build_context(self, kb_results: List[Dict], query: str = "") -> str:
        """构建知识库上下文文本"""
        if not kb_results:
            return "（暂无相关知识库资料，请基于你对中国旅游的广泛了解来回答）"

        parts = ["## 知识库资料\n"]
        for i, item in enumerate(kb_results, 1):
            snippet = self._extract_snippet(item["content"], query, 600) if query else item["content"][:600]
            parts.append(
                f"[{i}] 【{item['type']}】{item['title']} "
                f"（城市: {item['city']}，相关度: {item['score']:.0%}）\n"
                f"{snippet}\n"
            )
        return "\n".join(parts)

    def _extract_map_pois(self, kb_results: List[Dict]) -> List[Dict]:
        """从检索结果中提取可展示在地图上的 POI"""
        pois = []
        for item in kb_results:
            if item.get("longitude") and item.get("latitude"):
                pois.append({
                    "name": item["title"],
                    "longitude": item["longitude"],
                    "latitude": item["latitude"],
                    "type": item["type"],
                    "description": item.get("content", "")[:150],
                    "tags": item.get("tags", ""),
                })
        return pois[:5]  # 最多5个地图标记

    async def astream_chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        options: Optional[Dict] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式聊天：检索 + LLM 生成

        Args:
            message: 当前用户消息
            conversation_id: 会话 ID
            options: 额外选项
            history: 对话历史 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

        Yields:
            {"type": "token", "text": "..."}
            {"type": "citation", "kb_items": [...]}
            {"type": "map", "pois": [...]}
            {"type": "done", "token_count": N}
            {"type": "error", "code": "...", "message": "..."}
        """
        # 1. 检索知识库
        kb_results = self._search_knowledge(message, top_k=5)

        # 引用：仅知识库名称/城市匹配的高分结果（>=0.50）
        cite_results = [r for r in kb_results if r["score"] >= 0.50]

        # KB 无结果 → 联网搜索（仅作上下文，不显示为参考资料）
        is_web_search = False
        if not cite_results:
            web_results = self._search_web(message)
            if web_results:
                kb_results = web_results  # 只用作模型上下文
                is_web_search = True
                # 不设置 cite_results，联网搜索不显示参考资料

        # 地图：仅显示知识库中有坐标的地点
        if cite_results:
            map_pois = self._extract_map_pois(cite_results)
            if map_pois:
                yield {"type": "map", "pois": map_pois}

        # 参考资料：仅知识库匹配结果，联网搜索不显示
        if cite_results:
            yield {"type": "citation", "kb_items": [
                {
                    "id": r["id"], "title": r["title"], "type": r["type"],
                    "snippet": self._extract_snippet(r["content"], message, 250),
                    "score": r["score"],
                    "source_url": r.get("source_url", ""),
                }
                for r in cite_results
            ]}

        # 5. 构建 Prompt
        context = self._build_context(kb_results, message) if kb_results else ""
        current_date = datetime.now().strftime("%Y年%m月%d日")

        # 用户位置信息
        location_note = ""
        user_location = (options or {}).get("location")
        if user_location and user_location.get("city"):
            loc_city = user_location["city"]
            loc_lat = user_location.get("lat")
            loc_lng = user_location.get("lng")
            location_note = f"\n\n用户当前位置：{loc_city}"
            if loc_lat and loc_lng:
                location_note += f"（经纬度: {loc_lng}, {loc_lat}）"

        system_content = SYSTEM_PROMPT.format(current_date=current_date) + location_note
        if is_web_search:
            # 联网搜索结果仅作上下文，不要求引用
            user_content = f"{context}\n\n用户问题：{message}\n\n请参考以上联网搜索结果来回答，但不要使用引用标记。如果资料中没有精确坐标，仍要提供地址、交通方式等实用信息。"
        elif cite_results:
            user_content = f"{context}\n\n用户问题：{message}\n\n请基于以上知识库资料回答。引用时使用 [^编号] 标记。如果资料中没有精确坐标，仍要提供地址、交通方式等实用信息，并建议用户使用高德地图等应用进行精确导航。"
        else:
            user_content = f"用户问题：{message}\n\n请基于你对中国旅游的了解来回答，不要使用引用标记。"

        # 6. 构建完整消息列表（含历史对话）
        messages = [{"role": "system", "content": system_content}]
        if history:
            # 限制历史轮数，避免超出 token 限制
            recent_history = history[-10:]  # 最近 5 轮（10 条消息）
            messages.extend(recent_history)
            # 添加提示
            messages.append({"role": "system", "content": "以上是对话历史。请基于对话上下文，结合知识库资料回答用户的最新问题。"})
        messages.append({"role": "user", "content": user_content})

        # 7. 调用通义千问流式生成
        try:
            responses = Generation.call(
                model="qwen-turbo",
                messages=messages,
                result_format="message",
                stream=True,
                incremental_output=True,
                temperature=0.7,
                top_p=0.9,
                max_tokens=2048,
            )

            token_count = 0
            for response in responses:
                if response.status_code == HTTPStatus.OK:
                    choice = response.output.choices[0]
                    content = choice.message.content
                    if content:
                        token_count += 1
                        yield {"type": "token", "text": content}
                else:
                    yield {
                        "type": "error",
                        "code": f"API_ERROR_{response.status_code}",
                        "message": response.message or "大模型请求失败",
                    }
                    return

            yield {"type": "done", "token_count": token_count}

        except Exception as e:
            yield {
                "type": "error",
                "code": "LLM_ERROR",
                "message": f"AI 服务异常: {str(e)}",
            }
