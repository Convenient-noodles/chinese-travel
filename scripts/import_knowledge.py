"""
知识库批量导入脚本
将 JSON 数据导入到 SQLite 数据库和 ChromaDB 向量库
"""

import json
import os
import sys
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.database import async_session_factory, engine, Base
from app.models.knowledge import Attraction, Hotel, Food
import chromadb
from chromadb.utils import embedding_functions


def load_json(filepath):
    """加载 JSON 数据文件"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def import_to_database():
    """将种子数据导入到 SQLite 数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        async with session.begin():
            # 导入景点
            attractions_data = load_json(
                os.path.join(os.path.dirname(__file__), "..", "data", "attractions.json")
            )
            for item in attractions_data:
                # 检查是否已存在
                from sqlalchemy import select
                result = await session.execute(
                    select(Attraction).where(Attraction.name == item["name"])
                )
                if result.scalar_one_or_none():
                    continue
                attraction = Attraction(**item)
                session.add(attraction)
            print(f"[导入] 景点: {len(attractions_data)} 条")

            # 导入住宿
            hotels_data = load_json(
                os.path.join(os.path.dirname(__file__), "..", "data", "hotels.json")
            )
            for item in hotels_data:
                from sqlalchemy import select
                result = await session.execute(
                    select(Hotel).where(Hotel.name == item["name"])
                )
                if result.scalar_one_or_none():
                    continue
                hotel = Hotel(**item)
                session.add(hotel)
            print(f"[导入] 住宿: {len(hotels_data)} 条")

            # 导入美食
            foods_data = load_json(
                os.path.join(os.path.dirname(__file__), "..", "data", "foods.json")
            )
            for item in foods_data:
                from sqlalchemy import select
                result = await session.execute(
                    select(Food).where(Food.name == item["name"])
                )
                if result.scalar_one_or_none():
                    continue
                food = Food(**item)
                session.add(food)
            print(f"[导入] 美食: {len(foods_data)} 条")

    print("[导入] 数据库写入完成")


def import_to_chromadb():
    """将种子数据导入到 ChromaDB 向量库"""
    persist_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "backend", settings.CHROMA_PERSIST_DIR)
    )
    os.makedirs(persist_dir, exist_ok=True)

    # 使用 sentence-transformers 的中文模型（如果可用），否则使用默认模型
    try:
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="shibing624/text2vec-base-chinese"
        )
        print("[导入] 使用中文 Embedding 模型: shibing624/text2vec-base-chinese")
    except Exception:
        try:
            embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-small-zh-v1.5"
            )
            print("[导入] 使用中文 Embedding 模型: BAAI/bge-small-zh-v1.5")
        except Exception:
            embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            print("[导入] 使用默认 Embedding 模型 (英文，召回率可能较低)")

    client = chromadb.PersistentClient(path=persist_dir)

    # 为三类知识分别创建 Collection
    collections = {}
    for name in ["kb_attractions", "kb_hotels", "kb_foods"]:
        try:
            client.delete_collection(name)
        except Exception:
            pass
        collections[name] = client.create_collection(
            name=name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # 导入景点
    attractions_data = load_json(
        os.path.join(os.path.dirname(__file__), "..", "data", "attractions.json")
    )
    if attractions_data:
        ids = [f"attr_{i}" for i in range(len(attractions_data))]
        documents = [item["content"] for item in attractions_data]
        metadatas = [
            {
                "name": item["name"],
                "city": item["city"],
                "province": item.get("province", ""),
                "category": item.get("category", ""),
                "longitude": item.get("longitude"),
                "latitude": item.get("latitude"),
                "tags": item.get("tags", ""),
            }
            for item in attractions_data
        ]
        collections["kb_attractions"].add(
            ids=ids, documents=documents, metadatas=metadatas
        )
        print(f"[ChromaDB] 景点: {len(ids)} 条已索引")

    # 导入住宿
    hotels_data = load_json(
        os.path.join(os.path.dirname(__file__), "..", "data", "hotels.json")
    )
    if hotels_data:
        ids = [f"hotel_{i}" for i in range(len(hotels_data))]
        documents = [item["content"] for item in hotels_data]
        metadatas = [
            {
                "name": item["name"],
                "city": item["city"],
                "province": item.get("province", ""),
                "hotel_type": item.get("hotel_type", ""),
                "price_range": item.get("price_range", ""),
                "longitude": item.get("longitude"),
                "latitude": item.get("latitude"),
                "tags": item.get("tags", ""),
            }
            for item in hotels_data
        ]
        collections["kb_hotels"].add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"[ChromaDB] 住宿: {len(ids)} 条已索引")

    # 导入美食
    foods_data = load_json(
        os.path.join(os.path.dirname(__file__), "..", "data", "foods.json")
    )
    if foods_data:
        ids = [f"food_{i}" for i in range(len(foods_data))]
        documents = [item["content"] for item in foods_data]
        metadatas = [
            {
                "name": item["name"],
                "city": item["city"],
                "province": item.get("province", ""),
                "category": item.get("category", ""),
                "avg_price": item.get("avg_price", ""),
                "longitude": item.get("longitude"),
                "latitude": item.get("latitude"),
                "tags": item.get("tags", ""),
            }
            for item in foods_data
        ]
        collections["kb_foods"].add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"[ChromaDB] 美食: {len(ids)} 条已索引")

    print("[ChromaDB] 全部数据索引完成")


async def main():
    print("=" * 50)
    print("旅伴 — 知识库数据导入工具")
    print("=" * 50)

    # 1. 导入数据库
    await import_to_database()

    # 2. 导入 ChromaDB（在同步上下文中执行）
    import_to_chromadb()

    print("\n✅ 知识库导入完成！")


if __name__ == "__main__":
    asyncio.run(main())
