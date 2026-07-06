"""
认证业务逻辑：注册、登录、密码修改、管理员种子数据
"""

from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.config import settings


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    nickname: Optional[str] = None,
    email: Optional[str] = None,
) -> Tuple[Optional[User], Optional[str]]:
    """
    注册新用户
    返回: (user, error_message)
    """
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none() is not None:
        return None, f"用户名 '{username}' 已被注册"

    # 创建用户
    user = User(
        username=username,
        password_hash=hash_password(password),
        nickname=nickname or username,
        email=email,
        role="user",
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user, None


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Tuple[Optional[User], Optional[str]]:
    """
    用户登录认证
    返回: (user, error_message)
    """
    result = await db.execute(
        select(User).where(User.username == username, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if user is None:
        return None, "用户名或密码错误"

    if not verify_password(password, user.password_hash):
        return None, "用户名或密码错误"

    return user, None


async def change_password(
    db: AsyncSession,
    user: User,
    old_password: str,
    new_password: str,
) -> Tuple[bool, Optional[str]]:
    """
    修改密码：先验证旧密码，再更新为新密码
    返回: (success, error_message)
    """
    if not verify_password(old_password, user.password_hash):
        return False, "旧密码不正确"

    user.password_hash = hash_password(new_password)
    await db.flush()
    return True, None


def generate_tokens(user: User) -> dict:
    """为用户生成 Access Token 和 Refresh Token"""
    token_data = {"sub": user.id, "username": user.username, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def seed_admin_user(db: AsyncSession):
    """
    初始化管理员账号（仅当管理员账号不存在时创建）
    默认账号: admin / 123456
    """
    result = await db.execute(
        select(User).where(User.username == settings.ADMIN_USERNAME)
    )
    existing_admin = result.scalar_one_or_none()

    if existing_admin is None:
        admin = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            nickname="管理员",
            role="admin",
        )
        db.add(admin)
        await db.flush()
        print(f"[Seed] 管理员账号已创建: {settings.ADMIN_USERNAME}")
    else:
        print(f"[Seed] 管理员账号已存在，跳过")
