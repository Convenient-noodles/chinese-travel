"""
会话与消息相关 Pydantic 模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ConversationCreate(BaseModel):
    """创建会话请求"""
    title: Optional[str] = Field(None, max_length=200, description="会话标题（可选，默认自动生成）")


class ConversationUpdate(BaseModel):
    """更新会话请求"""
    title: Optional[str] = Field(None, max_length=200)
    status: Optional[str] = Field(None, description="active | archived")


class ConversationResponse(BaseModel):
    """会话响应"""
    id: str
    user_id: str
    title: str
    status: str
    message_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """消息响应"""
    id: str
    conversation_id: str
    role: str
    content: str
    citations: Optional[str] = None
    map_data: Optional[str] = None
    token_count: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatStreamRequest(BaseModel):
    """流式问答请求"""
    conversation_id: Optional[str] = Field(None, description="会话 ID（可选，新建会话时为空）")
    message: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    options: Optional[dict] = Field(
        default=None,
        description="额外选项: {city, budget, season, days, kb_types}"
    )


class ChatHistoryResponse(BaseModel):
    """对话历史响应"""
    conversation: ConversationResponse
    messages: List[MessageResponse]
