"""
数据库引擎与会话管理
支持 SQLite、MySQL、PostgreSQL 自动适配
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


def _get_connect_args() -> dict:
    """根据数据库类型返回不同的连接参数"""
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    elif url.startswith("mysql"):
        return {"charset": "utf8mb4"}
    return {}


def _get_pool_size() -> int:
    """根据数据库类型返回连接池大小"""
    if settings.DATABASE_URL.startswith("sqlite"):
        return 5
    return 20


# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=_get_connect_args(),
    pool_size=_get_pool_size(),
    max_overflow=10,
    pool_recycle=3600,
)

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
