"""
用户相关 Pydantic 请求/响应模型
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码（至少6位）")
    nickname: Optional[str] = Field(None, max_length=100, description="昵称")
    email: Optional[str] = Field(None, max_length=200, description="邮箱")

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v.strip()


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, max_length=100, description="密码")


class PasswordChangeRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码（至少6位）")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: str
    username: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    """刷新 Token 请求"""
    refresh_token: str


class MessageResponse(BaseModel):
    """通用消息响应"""
    status: str = "success"
    message: str
    data: Optional[dict] = None


# ========== 管理员用户管理 ==========

class UserStatsResponse(BaseModel):
    """用户注册统计数据"""
    total_users: int
    today_new: int
    week_new: int
    month_new: int
    admin_count: int
    active_count: int


class AdminUserItem(BaseModel):
    """管理员视角的用户列表项"""
    id: str
    username: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedUserResponse(BaseModel):
    """分页用户列表响应"""
    items: list[AdminUserItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminCreateUserRequest(BaseModel):
    """管理员创建用户请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码（至少6位）")
    nickname: Optional[str] = Field(None, max_length=100, description="昵称")
    email: Optional[str] = Field(None, max_length=200, description="邮箱")
    role: str = Field("user", pattern="^(user|admin)$", description="角色：user 或 admin")

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v.strip()


class UpdateUserRoleRequest(BaseModel):
    """修改用户角色请求"""
    role: str = Field(..., pattern="^(user|admin)$", description="新角色：user 或 admin")


class UpdateUserStatusRequest(BaseModel):
    """修改用户状态请求"""
    is_active: bool = Field(..., description="是否启用")
