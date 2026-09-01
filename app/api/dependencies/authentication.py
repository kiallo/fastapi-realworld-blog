from typing import Optional, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from app.core.config import get_app_settings
from app.api.dependencies.database import get_repository
from app.db.repositories.users import UsersRepository
from app.services.jwt import get_username_from_token
from app.models.domain.users import UserInDB

# ===== 自定义 APIKeyHeader =====

class RWAPIKeyHeader(APIKeyHeader):
    """RealWorld 风格的 API Key Header 提取器"""

    async def __call__(self, request: Request) -> Optional[str]:
        try:
            return await super().__call__(request)
        except HTTPException as http_exc:
            # 将 Starlette 的 HTTPException 转为 FastAPI 的格式
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="认证凭据缺失或无效",
            )


# ===== Token 前缀 =====

def get_token_from_header(
    api_key: str = Depends(
        RWAPIKeyHeader(name="Authorization", auto_error=False)
    ),
    settings=Depends(get_app_settings),
) -> str:
    """
    从 Authorization Header 提取 JWT Token

    Header 格式：Authorization: Token eyJhbGci...
    返回：去除前缀后的 Token 字符串
    """
    if not api_key:
        return ""
    
    token_prefix = f"{settings.jwt_token_prefix} "
    if not api_key.startswith(token_prefix):
        return ""

    return api_key[len(token_prefix):]


# ===== 必选认证 =====

async def get_current_user(
    token: str = Depends(get_token_from_header),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    settings=Depends(get_app_settings),
):
    """
    必选认证依赖 — 未认证返回 403

    依赖链：
    get_token_from_header → get_username_from_token → get_user_by_username
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要认证",
        )

    username = get_username_from_token(
        token=token,
        secret_key=settings.secret_key.get_secret_value(),
    )

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token 无效或已过期",
        )

    try:
        user = await users_repo.get_user_by_username(username=username)
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户不存在",
        )

    
def get_current_user_authorizer(
    *, required: bool = True
) -> Callable:
    """
    认证工厂函数

    required=True  → 未认证返回 403
    required=False → 未认证返回 None（允许匿名访问）

    使用示例：
    - 创建文章：Depends(get_current_user_authorizer())  # 必须登录
    - 文章列表：Depends(get_current_user_authorizer(required=False))  # 可选
    """
    return _get_current_user if required else _get_current_user_optional


async def _get_current_user(
    token: str = Depends(get_token_from_header),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    settings=Depends(get_app_settings),
) -> UserInDB:
    """必选认证 — 未认证抛 403"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要认证",
        )
    return await _resolve_user(token, users_repo, settings)


async def _get_current_user_optional(
    token: str = Depends(get_token_from_header),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    settings=Depends(get_app_settings),
) -> Optional[UserInDB]:
    """可选认证 — 未认证返回 None"""
    if not token:
        return None
    try:
        return await _resolve_user(token, users_repo, settings)
    except HTTPException:
        return None


async def _resolve_user(
    token: str,
    users_repo: UsersRepository,
    settings,
) -> UserInDB:
    """解析 Token → 查询用户"""
    username = get_username_from_token(
        token=token,
        secret_key=settings.secret_key.get_secret_value(),
    )

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token 无效或已过期",
        )

    try:
        return await users_repo.get_user_by_username(username=username)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户不存在",
        )