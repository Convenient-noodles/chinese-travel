"""
问答 API：SSE 流式聊天，RAG 检索增强生成
"""

import json
import asyncio
import time
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.schemas.conversation import ChatStreamRequest
from app.api.deps import get_current_user
from app.services.rag_service import RAGService

logger = logging.getLogger("chat")
router = APIRouter(prefix="/api/chat", tags=["AI 问答"])

# RAG 服务单例
rag_service = RAGService()


def _format_sse(event: str, data: dict | str) -> str:
    """格式化为 SSE 消息"""
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


async def _save_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    citations: list = None,
    map_data: dict = None,
    token_count: int = 0,
) -> Message:
    """保存消息到数据库"""
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        citations=json.dumps(citations, ensure_ascii=False) if citations else None,
        map_data=json.dumps(map_data, ensure_ascii=False) if map_data else None,
        token_count=token_count,
    )
    db.add(msg)

    # 更新会话消息计数和更新时间
    from sqlalchemy import update
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(
            message_count=Conversation.message_count + 2,  # user + assistant
            updated_at=Conversation.updated_at,  # 触发 onupdate
        )
    )

    await db.flush()
    await db.refresh(msg)
    return msg


@router.post("/stream", summary="流式问答（SSE）")
async def chat_stream(
    req: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    核心问答接口：接收用户消息，返回 SSE 流式回答

    SSE 事件类型：
    - token: 逐字输出文本
    - citation: 知识库引用信息
    - map: 地图标记数据
    - done: 回答完成
    - error: 错误信息
    """
    # 验证/自动创建会话
    conv = None
    if req.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == req.conversation_id,
                Conversation.user_id == current_user.id,
                Conversation.status == "active",
            )
        )
        conv = result.scalar_one_or_none()

    # 会话不存在或未提供 → 自动创建
    if conv is None:
        conv = Conversation(
            user_id=current_user.id,
            title="新的旅游咨询",
        )
        db.add(conv)
        await db.flush()
        await db.refresh(conv)

    async def generate() -> AsyncGenerator[str, None]:
        full_content = ""
        citations = []
        map_pois = []
        token_count = 0
        conv_id = conv.id
        t_start = time.time()

        try:
            # 0. 加载对话历史
            history = []
            if conv_id:
                hist_result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conv_id)
                    .order_by(Message.created_at)
                    .limit(20)  # 最近 20 条消息
                )
                for msg in hist_result.scalars().all():
                    history.append({"role": msg.role, "content": msg.content})

            # 1. 先保存用户消息
            user_msg = await _save_message(
                db, conv_id,
                role="user", content=req.message,
            )

            # 2. 如果是第一条消息，自动生成会话标题
            if conv and conv.message_count == 2:
                title = req.message[:30] if len(req.message) <= 30 else req.message[:27] + "..."
                from sqlalchemy import update as sql_update
                await db.execute(
                    sql_update(Conversation)
                    .where(Conversation.id == conv_id)
                    .values(title=title)
                )

            # 3. 使用 RAG Service 进行检索增强生成
            async for chunk in rag_service.astream_chat(
                message=req.message,
                conversation_id=conv_id,
                history=history,
                options=req.options or {},
            ):
                event_type = chunk.get("type", "token")

                if event_type == "token":
                    full_content += chunk.get("text", "")
                    token_count += 1
                    yield _format_sse("token", {"text": chunk.get("text", "")})

                elif event_type == "citation":
                    citations = chunk.get("kb_items", [])
                    yield _format_sse("citation", {"kb_items": citations})

                elif event_type == "map":
                    map_pois = chunk.get("pois", [])
                    yield _format_sse("map", {"type": "poi", "pois": map_pois})

                elif event_type == "done":
                    token_count = chunk.get("token_count", token_count)
                    break

                elif event_type == "error":
                    yield _format_sse("error", {
                        "code": chunk.get("code", "UNKNOWN"),
                        "message": chunk.get("message", "未知错误"),
                    })
                    return

            # 4. 保存 AI 回答
            assistant_msg = await _save_message(
                db, conv_id,
                role="assistant",
                content=full_content,
                citations=citations,
                map_data={"type": "poi", "pois": map_pois} if map_pois else None,
                token_count=token_count,
            )

            elapsed = time.time() - t_start
            logger.info(f"[chat/stream] done user={current_user.id} conv={conv_id} tokens={token_count} elapsed={elapsed:.1f}s")
            yield _format_sse("done", {
                "message_id": assistant_msg.id,
                "conversation_id": conv_id,
                "token_count": token_count,
                "elapsed_ms": int(elapsed * 1000),
            })

        except Exception as e:
            elapsed = time.time() - t_start
            logger.error(f"[chat/stream] user={current_user.id} conv={conv_id} elapsed={elapsed:.1f}s error={e}")
            yield _format_sse("error", {
                "code": "STREAM_ERROR",
                "message": str(e),
            })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )
