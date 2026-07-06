"""
应用配置管理
使用 pydantic-settings 从环境变量 / .env 文件加载配置
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """应用全局配置"""

    # --- 应用 ---
    APP_NAME: str = "旅伴 - 中国旅游推荐助手"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:8080,http://127.0.0.1:8080"

    # --- 数据库 ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./tourism.db"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- 通义千问 (DashScope) ---
    DASHSCOPE_API_KEY: str = ""

    # --- JWT ---
    JWT_SECRET: str = "change-this-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- 高德地图 ---
    AMAP_API_KEY: str = ""
    AMAP_BASE_URL: str = "https://restapi.amap.com/v3"

    # --- ChromaDB ---
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # --- 管理员初始账号 ---
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "123456"

    @property
    def cors_origin_list(self) -> List[str]:
        """解析 CORS 来源列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def is_sqlite(self) -> bool:
        """判断是否使用 SQLite"""
        return self.DATABASE_URL.startswith("sqlite")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Also search parent directory for .env
        extra = "allow"


# 全局单例配置
settings = Settings()
