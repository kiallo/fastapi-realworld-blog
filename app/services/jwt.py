import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from pydantic import ValidationError
from app.models.schemas.jwt import JWTMeta, JWTUser


def generate_session_id() -> str:
    """
    生成会话 ID（sid）

    为什么白名单里存 sid 而不是 token 原文：
    ① token 原文是"可以直接用的凭据"，Redis 一泄漏就等于把凭据复制了一份；
       sid 是随机串，泄漏了也换不出可用的 token
    ② sid 只有 43 个字符，JWT 原文 200+，Redis 里省内存
    """
    return secrets.token_urlsafe(32)


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
    session_id: Optional[str] = None,
) -> str:
    """为用户创建访问 Token

    除用户名外还写入一个 sid（会话 ID）：
    认证时用它去 Redis 白名单比对，而不是拿 token 原文比对。
    session_id 不传则自动生成。
    """
    return create_jwt_token(
        jwt_content={
            "username": user_username,
            "sid": session_id or generate_session_id(),
        },
        secret_key=secret_key,
        expires_delta=expires_delta,
    )


def _decode_token_payload(
    *,
    token: str,
    secret_key: str,
) -> Optional[dict]:
    """验签 + 验过期；任何问题（过期/签名错/格式错）统一返回 None"""
    try:
        return jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except jwt.PyJWTError:
        return None


def get_user_from_token(
    *,
    token: str,
    secret_key: str,
) -> Optional[JWTUser]:
    """
    从 Token 中解析出用户信息（用户名 + 会话 ID）

    返回 None 的情况：
    - Token 过期 / 签名无效 / 格式错误
    - Token 里没有 sid（例如改造前签发的老 Token，会被当成无效）
    """
    payload = _decode_token_payload(token=token, secret_key=secret_key)
    if payload is None:
        return None

    try:
        return JWTUser(
            username=payload["username"],
            session_id=payload["sid"],
        )
    except (ValidationError, KeyError):
        return None


def get_username_from_token(
    *,
    token: str,
    secret_key: str,
) -> Optional[str]:
    """
    从 Token 中提取用户名（只关心用户名时的便捷函数）

    ⚠️ 注意：它只验签，**不查 Redis 白名单**，也不要求 Token 里一定有 sid。
    认证依赖里请用 get_user_from_token + is_session_valid 组合。
    """
    payload = _decode_token_payload(token=token, secret_key=secret_key)
    if payload is None:
        return None
    return payload.get("username")