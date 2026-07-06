"""
知识库 Pydantic 模型
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class KnowledgeCreate(BaseModel):
    """新增/导入知识条目"""
    name: str = Field(..., min_length=1, max_length=200)
    item_type: str = Field(default="attraction")  # attraction / hotel / food
    city: str = Field(default="")
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    status: Optional[str] = "published"


class KnowledgeUpdate(BaseModel):
    """更新知识条目（全部可选）"""
    name: Optional[str] = Field(None, max_length=200)
    item_type: Optional[str] = None
    city: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    status: Optional[str] = None


class KnowledgeResponse(BaseModel):
    """知识条目响应"""
    id: str
    name: str
    item_type: str
    city: str
    description: Optional[str] = None
    content: str
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchImportRequest(BaseModel):
    """批量导入请求 — 解析结构化文本"""
    content: str = Field(..., min_length=1, description="包含 === 类型：名称 === 块的结构化文本")


class BatchImportResponse(BaseModel):
    """批量导入结果"""
    success_count: int
    failed_count: int
    items: list[dict]  # 成功导入的条目摘要


class PaginatedResponse(BaseModel):
    """分页响应"""
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
