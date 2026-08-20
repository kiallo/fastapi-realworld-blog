from typing import Optional
from pydantic import Field
from app.models.schemas.rwschema import RWSchema


# ===== 请求 Schema =====

class UserInCreate(RWSchema):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=100)


class UserInLogin(RWSchema):
    """用户登录请求"""
    email: str
    password: str


class UserInUpdate(RWSchema):
    """用户资料更新请求 — 所有字段可选"""
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    bio: Optional[str] = None
    image: Optional[str] = None


# ===== 响应 Schema =====

class UserForResponse(RWSchema):
    """对外暴露的用户信息（不含密码）"""
    username: str
    email: str
    bio: str = ""
    image: Optional[str] = None
    token: str = ""  # JWT token


class UserWithToken(RWSchema):
    """用户 + Token 组合响应"""
    username: str
    email: str
    bio: str = ""
    image: Optional[str] = None
    token: str


class UserInResponse(RWSchema):
    """{ "user": {...} } 包装格式 — RealWorld API 规范"""
    user: UserWithToken

