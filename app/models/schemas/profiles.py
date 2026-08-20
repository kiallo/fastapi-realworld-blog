from typing import Optional
from app.models.schemas.rwschema import RWSchema


class ProfileForResponse(RWSchema):
    """用户资料响应"""
    username: str
    bio: str = ""
    image: Optional[str] = None
    following: bool = False


class ProfileInResponse(RWSchema):
    """{ "profile": {...} } 包装格式"""
    profile: ProfileForResponse