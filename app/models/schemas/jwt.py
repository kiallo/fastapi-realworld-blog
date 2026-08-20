from app.models.schemas.rwschema import RWSchema


class JWTMeta(RWSchema):
    """JWT 元数据"""
    exp: int  # 过期时间戳
    sub: str  # 主题（通常="access"）


class JWTUser(RWSchema):
    """JWT 中携带的用户信息"""
    username: str


class JWTToken(RWSchema):
    """完整的 JWT Token 结构"""
    token_type: str = "bearer"
    access_token: str