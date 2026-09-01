from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from pydantic import ValidationError
from app.models.schemas.jwt import JWTMeta, JWTUser


def create_jwt_token(
    *,
    jwt_content: dict,
    secret_key: str,
    expires_delta: timedelta,
) -> str:
    """
    创建 JWT Token

    JWT 结构：Header.Payload.Signature
    - Header：算法声明（HS256）
    - Payload：业务数据 + 过期时间
    - Signature：防盗改签名
    """
    to_encode = jwt_content.copy()
    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    to_encode.update({
        "exp": expire,           # 过期时间（Unix 时间戳）
        "iat": now,              # 签发时间
        "sub": "access",         # 主题
    })

    return jwt.encode(
        to_encode,
        secret_key,
        algorithm="HS256",
    )


def create_access_token_for_user(
    *,
    user_username: str,
    secret_key: str,
    expires_delta: timedelta,
) -> str:
    """为用户创建访问 Token"""
    return create_jwt_token(
        jwt_content={"username": user_username},
        secret_key=secret_key,
        expires_delta=expires_delta,
    )


def get_username_from_token(
    *,
    token: str,
    secret_key: str,
) -> Optional[str]:
    """
    从 Token 中提取用户名

    返回 None 的情况：
    - Token 过期
    - Token 签名无效
    - Token 格式错误
    """
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
        jwt_user = JWTUser(username=payload["username"])
        return jwt_user.username
    except (jwt.PyJWTError, ValidationError, KeyError):
        return None