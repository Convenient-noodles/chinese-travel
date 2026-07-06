"""
知识库管理 API（管理员专用）
统一 CRUD + 文件直接导入
"""

import uuid, re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.knowledge import KnowledgeItem
from app.schemas.knowledge import (
    KnowledgeCreate, KnowledgeUpdate, KnowledgeResponse,
    BatchImportRequest, BatchImportResponse, PaginatedResponse,
)
from app.api.deps import require_admin

router = APIRouter(prefix="/api/admin/knowledge", tags=["知识库管理"])


# ============================================================
# 列表查询
# ============================================================

@router.get("", summary="知识库列表")
async def list_knowledge(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    search: Optional[str] = None,
    item_type: Optional[str] = None,
    city: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """分页查询知识库"""
    conditions = [KnowledgeItem.status == "published"]
    if search:
        conditions.append(
            or_(KnowledgeItem.name.contains(search), KnowledgeItem.content.contains(search))
        )
    if item_type:
        conditions.append(KnowledgeItem.item_type == item_type)
    if city:
        conditions.append(KnowledgeItem.city == city)

    from sqlalchemy import and_
    where_clause = and_(*conditions)

    total = (await db.execute(
        select(func.count()).select_from(KnowledgeItem).where(where_clause)
    )).scalar() or 0

    query = (
        select(KnowledgeItem).where(where_clause)
        .order_by(KnowledgeItem.updated_at.desc())
        .limit(page_size).offset((page - 1) * page_size)
    )
    items = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[KnowledgeResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


# ============================================================
# 批量导入 — 解析 === 类型：名称 === 结构化文本
# ============================================================

TYPE_MAP = {"景点": "attraction", "住宿": "hotel", "美食": "food"}

# 匹配 === 类型：名称 === 及其后续内容块
BLOCK_PATTERN = re.compile(
    r'===\s*(景点|住宿|美食)\s*[：:]\s*(.+?)\s*===\s*\n(.*?)(?=\n===|\n##|\Z)',
    re.DOTALL
)


@router.post("/batch-import", response_model=BatchImportResponse, summary="批量导入（解析结构化文本）")
async def batch_import_knowledge(
    data: BatchImportRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    解析包含 === 景点：XXX === / === 住宿：XXX === / === 美食：XXX === 格式的文本，
    自动拆分为独立知识条目，提取城市、描述、经纬度等字段
    """
    content = data.content
    matches = list(BLOCK_PATTERN.finditer(content))

    if not matches:
        raise HTTPException(status_code=400, detail="未找到任何有效的 === 类型：名称 === 格式内容块")

    imported = []
    failed = 0

    for m in matches:
        item_type_cn = m.group(1)
        name = m.group(2).strip()
        block = m.group(3).strip()

        item_type = TYPE_MAP.get(item_type_cn, "attraction")

        # 提取各字段
        city_match = re.search(r'城市[：:]\s*(.+)', block)
        desc_match = re.search(r'描述[：:]\s*(.+)', block)
        coord_match = re.search(r'经纬度[：:]\s*([\d.]+)\s*[,，]\s*([\d.]+)', block)

        city = city_match.group(1).strip() if city_match else ""
        description = desc_match.group(1).strip() if desc_match else ""
        lng = float(coord_match.group(1)) if coord_match else None
        lat = float(coord_match.group(2)) if coord_match else None

        # 构建完整内容
        full_content = f"名称：{name}\n城市：{city}\n描述：{description}\n---\n{block}"

        try:
            item = KnowledgeItem(
                id=str(uuid.uuid4()),
                name=name,
                item_type=item_type,
                city=city,
                description=description,
                content=full_content if len(full_content) < 10000 else block,
                longitude=lng,
                latitude=lat,
                status="published",
            )
            db.add(item)
            imported.append({"name": name, "city": city, "item_type": item_type,
                           "longitude": lng, "latitude": lat})
        except Exception as e:
            print(f"[BatchImport] 导入 {name} 失败: {e}")
            failed += 1

    await db.flush()

    return BatchImportResponse(
        success_count=len(imported),
        failed_count=failed,
        items=imported,
    )


# ============================================================
# 单个 CRUD
# ============================================================

@router.get("/{item_id}", response_model=KnowledgeResponse, summary="详情")
async def get_knowledge(
    item_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    return KnowledgeResponse.model_validate(item)


@router.post("", response_model=KnowledgeResponse, status_code=201, summary="新增")
async def create_knowledge(
    data: KnowledgeCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    item = KnowledgeItem(**data.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return KnowledgeResponse.model_validate(item)


@router.put("/{item_id}", response_model=KnowledgeResponse, summary="更新")
async def update_knowledge(
    item_id: str, data: KnowledgeUpdate,
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await db.flush()
    await db.refresh(item)
    return KnowledgeResponse.model_validate(item)


@router.delete("/{item_id}", summary="删除")
async def delete_knowledge(
    item_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.delete(item)
    await db.flush()
    return {"status": "success", "message": "已删除"}
