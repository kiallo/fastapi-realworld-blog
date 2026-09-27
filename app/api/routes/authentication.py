from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.config import get_app_settings
from app.api.dependencies.database import get_repository
from app.api.dependencies.authentication import get_current_user_authorizer, get_token_from_header
from app.core.dependencies import get_token_storage
from app.db.repositories.users import UsersRepository
from app.models.schemas.users import (
    UserInCreate, UserInLogin, UserInResponse, UserWithToken,
)
from app.models.domain.users import UserInDB
from app.services.authentication import (
    check_username_is_taken, check_email_is_taken,
)
from app.services.jwt import create_access_token_for_user
from app.services.token_storage import TokenStorage

router = APIRouter(prefix="/users", tags=["authentication"])


def _create_user_response(user: UserInDB, token: str) -> UserInResponse:
    """构造用户响应（{ "user": { ... } } 格式）"""
    return UserInResponse(
        user=UserWithToken(
            username=user.username,
            email=user.email,
            bio=user.bio,
            image=user.image,
            token=token,
        )
    )


def _get_device_info(request: Request) -> str:
    """从请求中提取设备信息"""
    user_agent = request.headers.get("User-Agent", "unknown")
    # 简化处理，取前100字符
    return user_agent[:100]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserInResponse)
async def register(
    request: Request,
    user_create: UserInCreate,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    settings=Depends(get_app_settings),
    token_storage: TokenStorage = Depends(get_token_storage),
):
    """
    用户注册

    流程：
    1. 校验用户名和邮箱是否已存在
    2. 创建用户（Repository 内生成 salt + hash）
    3. 签发 JWT Token
    4. 返回用户信息 + Token
    """
    # 检查用户名
    if await check_username_is_taken(users_repo, user_create.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被占用",
        )

    # 检查邮箱
    if await check_email_is_taken(users_repo, user_create.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )

    # 创建用户
    user = await users_repo.create_user(
        username=user_create.username,
        email=user_create.email,
        password=user_create.password,
    )

    # 签发 Token
    token = create_access_token_for_user(
        user_username=user.username,
        secret_key=settings.secret_key.get_secret_value(),
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    # 存储到 Redis
    await token_storage.store_token(
        username=user.username,
        token=token,
        expire_seconds=settings.access_token_expire_minutes * 60,
        device_info=_get_device_info(request),
    )

    return _create_user_response(user, token)


@router.post("/login", response_model=UserInResponse)
async def login(
    request: Request,
    user_login: UserInLogin,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    settings=Depends(get_app_settings),
    token_storage: TokenStorage = Depends(get_token_storage),
):
    """
    用户登录

    流程：
    1. 根据邮箱查询用户
    2. 验证密码
    3. 签发 JWT Token
    4. 返回用户信息 + Token

    安全设计：登录失败统一返回 "邮箱或密码错误"
    （不区分"邮箱不存在"和"密码错误"，防止撞库攻击）
    """
    # 查询用户
    try:
        user = await users_repo.get_user_by_email(email=user_login.email)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱或密码错误",
        )

    # 验证密码
    if not user.check_password(user_login.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱或密码错误",
        )

    # 签发 Token
    token = create_access_token_for_user(
        user_username=user.username,
        secret_key=settings.secret_key.get_secret_value(),
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    # 存储到 Redis（覆盖旧 Token，实现单设备登录）
    await token_storage.store_token(
        username=user.username,
        token=token,
        expire_seconds=settings.access_token_expire_minutes * 60,
        device_info=_get_device_info(request),
    )

    return _create_user_response(user, token)


@router.get("/me", response_model=UserInResponse)
async def get_current_user_info(
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    token: str = Depends(get_token_from_header), 
):
    """获取当前登录用户信息"""
    return _create_user_response(current_user, token)


@router.post("/logout")
async def logout(
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    token_storage: TokenStorage = Depends(get_token_storage),
):
    """
    用户登出

    从 Redis 中删除用户的 Token，使其立即失效
    """
    revoked = await token_storage.revoke_token(current_user.username)
    if revoked:
        return {"message": "登出成功"}
    else:
        return {"message": "未找到活跃会话"}