"""
数据库引擎与会话管理
支持 SQLite、MySQL、PostgreSQL 自动适配
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


def _get_connect_args() -> dict:
    """根据数据库类型返回不同的连接参数"""
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        return {
            "check_same_thread": False,
            "timeout": 30,  # 写锁等待 30 秒（并发场景下避免 immediate "database is locked"）
        }
    elif url.startswith("mysql"):
        return {"charset": "utf8mb4"}
    return {}


def _get_pool_size() -> int:
    """根据数据库类型返回连接池大小"""
    if settings.DATABASE_URL.startswith("sqlite"):
        return 50  # 压测场景：支持 100 并发
    return 20


# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # 压测时关闭 SQL 日志
    connect_args=_get_connect_args(),
    pool_size=_get_pool_size(),
    max_overflow=50,
    pool_recycle=3600,
    pool_pre_ping=True,
)


# 为 SQLite 启用 WAL 模式（写前日志：允许读写并发，大幅减少 "database is locked"）
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=60000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")       # 大幅提升写入性能
        cursor.execute("PRAGMA cache_size=-8000;")          # 8MB 缓存
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

# SQLite 写入并发限制：避免 30 个协程同时争抢写锁
# SQLite 只支持单写者，并发写入会导致 busy_timeout 排队
# 通过信号量限制并发数据库会话数，减少锁竞争
if settings.DATABASE_URL.startswith("sqlite"):
    _db_semaphore = asyncio.Semaphore(10)  # 最多 10 个并发数据库操作
else:
    _db_semaphore = None

# 异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# SQLAlchemy 声明式基类
class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话（每个请求一个会话）"""
    if _db_semaphore:
        async with _db_semaphore:
            async with async_session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()
    else:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


async def init_db():
    """初始化数据库：创建所有表 + 种子数据（管理员账号等）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 导入种子数据逻辑（避免循环导入）
    from app.services.auth_service import seed_admin_user
    async with async_session_factory() as session:
        async with session.begin():
            await seed_admin_user(session)
