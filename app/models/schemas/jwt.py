from pydantic import Field

from app.models.schemas.rwschema import RWSchema


class JWTMeta(RWSchema):
    """JWT 元数据"""
    exp: int  # 过期时间戳
    sub: str  # 主题（通常="access"）


class JWTUser(RWSchema):
    """JWT 中携带的用户信息"""
    username: str

    # ★ 会话 ID（claim 名固定写成 "sid"，不走 camelCase 生成器）
    #   认证时拿它去 Redis 白名单比对，而不是拿 token 原文比对
    session_id: str = Field(alias="sid")


class JWTToken(RWSchema):
    """完整的 JWT Token 结构"""
    token_type: str = "bearer"
    access_token: str