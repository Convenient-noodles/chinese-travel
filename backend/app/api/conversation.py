"""
会话管理 API：创建、列表、详情、删除会话
"""

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
    ChatHistoryResponse,
)
from app.schemas.knowledge import PaginatedResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["会话管理"])


@router.get("", response_model=PaginatedResponse, summary="获取会话列表")
async def list_conversations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有会话（按更新时间倒序）"""
    # 总数
    count_query = select(func.count()).where(
        Conversation.user_id == current_user.id,
        Conversation.status == "active",
    )
    total = (await db.execute(count_query)).scalar() or 0

    # 分页查询
    query = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id, Conversation.status == "active")
        .order_by(desc(Conversation.updated_at))
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()

    return PaginatedResponse(
        items=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("", response_model=ConversationResponse, summary="创建新会话")
async def create_conversation(
    req: Optional[ConversationCreate] = Body(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为用户创建一个新的咨询会话"""
    conv = Conversation(
        user_id=current_user.id,
        title=req.title if req and req.title else "新的旅游咨询",
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.get("/{conv_id}", response_model=ChatHistoryResponse, summary="获取会话详情")
async def get_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话详情及所有消息历史"""
    # 查询会话
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    # 查询消息
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return ChatHistoryResponse(
        conversation=ConversationResponse.model_validate(conv),
        messages=[MessageResponse.model_validate(m) for m in messages],
    )


@router.put("/{conv_id}", response_model=ConversationResponse, summary="更新会话")
async def update_conversation(
    conv_id: str,
    req: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新会话标题或状态"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    if req.title is not None:
        conv.title = req.title
    if req.status is not None:
        conv.status = req.status

    await db.flush()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.delete("/{conv_id}", summary="删除会话")
async def delete_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """软删除会话（标记为 archived）"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    conv.status = "archived"
    await db.flush()
    return {"status": "success", "message": "会话已删除"}
