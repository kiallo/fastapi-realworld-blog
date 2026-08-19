from typing import Optional
from app.models.domain.rwmodel import RWModel


class Profile(RWModel):
    """用户公开资料 — 不含密码等敏感字段"""
    username: str
    bio: str = ""
    image: Optional[str] = None
    following: bool = False