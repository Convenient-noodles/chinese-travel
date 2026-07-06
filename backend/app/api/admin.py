"""
管理员 API 路由：用户管理、统计数据
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    AdminUserItem,
    UserStatsResponse,
    PaginatedUserResponse,
    AdminCreateUserRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UserResponse,
    MessageResponse,
)
from app.api.deps import require_admin
from app.core.security import hash_password

router = APIRouter(prefix="/api/admin", tags=["管理员"])


@router.get("/users/stats", response_model=UserStatsResponse, summary="用户注册统计")
async def get_user_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取用户注册统计数据：总数、今日新增、本周新增、本月新增等"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    # 总用户数
    total = (await db.execute(
        select(func.count()).select_from(User)
    )).scalar() or 0

    # 今日新增
    today_new = (await db.execute(
        select(func.count()).select_from(User).where(User.created_at >= today_start)
    )).scalar() or 0

    # 本周新增
    week_new = (await db.execute(
        select(func.count()).select_from(User).where(User.created_at >= week_start)
    )).scalar() or 0

    # 本月新增
    month_new = (await db.execute(
        select(func.count()).select_from(User).where(User.created_at >= month_start)
    )).scalar() or 0

    # 管理员数量
    admin_count = (await db.execute(
        select(func.count()).select_from(User).where(User.role == "admin")
    )).scalar() or 0

    # 活跃用户数
    active_count = (await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )).scalar() or 0

    return UserStatsResponse(
        total_users=total,
        today_new=today_new,
        week_new=week_new,
        month_new=month_new,
        admin_count=admin_count,
        active_count=active_count,
    )


@router.get("/users", response_model=PaginatedUserResponse, summary="用户列表")
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索用户名或昵称"),
    role: Optional[str] = Query(None, description="按角色筛选"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """分页查询所有注册用户（管理员专用）"""
    conditions = []

    if search:
        conditions.append(
            User.username.contains(search) | User.nickname.contains(search)
        )
    if role:
        conditions.append(User.role == role)

    from sqlalchemy import and_
    where_clause = and_(*conditions) if conditions else None

    # 总数
    count_query = select(func.count()).select_from(User)
    if where_clause is not None:
        count_query = count_query.where(where_clause)
    total = (await db.execute(count_query)).scalar() or 0

    # 分页查询
    query = select(User).order_by(User.created_at.desc())
    if where_clause is not None:
        query = query.where(where_clause)
    query = query.limit(page_size).offset((page - 1) * page_size)

    users = (await db.execute(query)).scalars().all()

    return PaginatedUserResponse(
        items=[AdminUserItem.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("/users", response_model=UserResponse, status_code=201, summary="管理员创建用户")
async def create_user(
    data: AdminCreateUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员直接创建新用户（可指定角色为 admin 或 user）"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"用户名 '{data.username}' 已被注册",
        )

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        nickname=data.nickname or data.username,
        email=data.email,
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/role", response_model=UserResponse, summary="修改用户角色")
async def update_user_role(
    user_id: str,
    data: UpdateUserRoleRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """修改指定用户的角色（提升为管理员 / 降级为普通用户）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不允许修改自己的角色
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")

    user.role = data.role
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/status", response_model=UserResponse, summary="启用/禁用用户")
async def update_user_status(
    user_id: str,
    data: UpdateUserStatusRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """启用或禁用指定用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不允许禁用自己
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")

    user.is_active = data.is_active
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)
