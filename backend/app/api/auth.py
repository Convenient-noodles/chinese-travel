"""
认证 API 路由：注册、登录、修改密码、获取用户信息
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    PasswordChangeRequest,
    UserResponse,
    TokenResponse,
    TokenRefreshRequest,
    MessageResponse,
)
from app.services.auth_service import (
    register_user,
    authenticate_user,
    change_password,
    generate_tokens,
)
from app.api.deps import get_current_user
from app.core.security import decode_token

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=MessageResponse, summary="用户注册")
async def register(req: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户账号"""
    user, error = await register_user(
        db, req.username, req.password, req.nickname, req.email
    )
    if error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)

    return MessageResponse(
        message="注册成功",
        data={
            "user_id": user.id,
            "username": user.username,
        },
    )


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(req: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录，返回 Access Token 和 Refresh Token"""
    user, error = await authenticate_user(db, req.username, req.password)
    if error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error)

    tokens = generate_tokens(user)

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse, summary="刷新 Token")
async def refresh_token(req: TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    """使用 Refresh Token 获取新的 Access Token"""
    payload = decode_token(req.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Refresh Token",
        )

    user_id = payload.get("sub")
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )

    tokens = generate_tokens(user)
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的个人信息"""
    return UserResponse.model_validate(current_user)


@router.put("/password", response_model=MessageResponse, summary="修改密码")
async def update_password(
    req: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户的登录密码（需验证旧密码）"""
    success, error = await change_password(db, current_user, req.old_password, req.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    return MessageResponse(message="密码修改成功，请使用新密码重新登录")


@router.post("/logout", response_model=MessageResponse, summary="登出")
async def logout(current_user: User = Depends(get_current_user)):
    """
    登出当前用户。
    注意：当前实现为客户端清除 token，服务端不做额外处理。
    生产环境可将 token 加入 Redis 黑名单。
    """
    return MessageResponse(message="已登出")
