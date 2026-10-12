from typing import Optional, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from app.core.config import get_app_settings
from app.api.dependencies.database import get_repository
from app.core.dependencies import get_token_storage
from app.db.repositories.users import UsersRepository
from app.services.jwt import get_user_from_token
from app.models.domain.users import UserInDB
from app.services.token_storage import TokenStorage

# ===== 自定义 APIKeyHeader =====

class RWAPIKeyHeader(APIKeyHeader):
    """RealWorld 风格的 API Key Header 提取器"""

    async def __call__(self, request: Request) -> Optional[str]:
        try:
            return await super().__call__(request)
        except HTTPException as http_exc:
            # 将 Starlette 的 HTTPException 转为 FastAPI 的格式
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
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


# ===== ★ 唯一的认证实现 =====

async def _authenticate(
    token: str,
    users_repo: UsersRepository,
    token_storage: TokenStorage,
    settings,
) -> UserInDB:
    """
    认证的唯一实现 —— 必选和可选认证都走这里

    流程（四步，面试要能背）：
    1. Header 里有没有 Token
    2. JWT 验签 + 验过期 → 拿到 username 和 sid
    3. 拿 sid 查 Redis 白名单 → 登出/被踢的用户在这里被拦下
    4. 查库拿完整用户对象

    ⚠️ 设计要点：**失败一律抛 HTTPException**。
    "未登录时抛异常还是返回 None"是调用方的选择，
    不应该在认证逻辑里写成两套 —— 这就是改造前
    可选认证漏掉白名单校验的根因。
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要认证",
        )

    # 解析 JWT：验签 + 验过期，同时取出会话 ID
    jwt_user = get_user_from_token(
        token=token,
        secret_key=settings.secret_key.get_secret_value(),
    )

    if jwt_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        )

    # ★ Redis 白名单：可选认证也必须过这一关
    is_valid = await token_storage.is_session_valid(
        jwt_user.username, jwt_user.session_id,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已失效，请重新登录",
        )

    try:
        return await users_repo.get_user_by_username(username=jwt_user.username)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )


def get_current_user_authorizer(
    *, required: bool = True
) -> Callable:
    """
    认证工厂函数

    required=True  → 未认证抛 401
    required=False → 未认证返回 None（允许匿名访问）

    使用示例：
    - 创建文章：Depends(get_current_user_authorizer())  # 必须登录
    - 文章列表：Depends(get_current_user_authorizer(required=False))  # 可选
    """
    return _get_current_user if required else _get_current_user_optional


async def _get_current_user(
    token: str = Depends(get_token_from_header),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    token_storage: TokenStorage = Depends(get_token_storage),
    settings=Depends(get_app_settings),
) -> UserInDB:
    """必选认证 — 未登录/票据失效一律 401"""
    return await _authenticate(token, users_repo, token_storage, settings)


async def _get_current_user_optional(
    token: str = Depends(get_token_from_header),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    token_storage: TokenStorage = Depends(get_token_storage),
    settings=Depends(get_app_settings),
) -> Optional[UserInDB]:
    """
    可选认证 — 未登录返回 None

    与其他实现共用同一个 _authenticate，**区别只在失败时怎么办**：
    这里把"失败"翻译成 None，而不是跳过校验。
    所以登出后的旧 token 拿到这里也是匿名，不会出现
    "登出了但列表接口还认得我"的不一致。
    """
    if not token:
        return None
    try:
        return await _authenticate(token, users_repo, token_storage, settings)
    except HTTPException:
        return None
