from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
import asyncio
import asyncpg
import redis.asyncio as redis
from app.api.dependencies.database import get_connection_from_pool, get_repository
from app.core.dependencies import get_redis
from app.db.repositories.users import UsersRepository
from app.api.dependencies.authentication import get_current_user_authorizer
from app.models.domain.users import UserInDB

router = APIRouter()


@router.get("/")
async def root():
    """根路径 - 健康检查"""
    return {"message": "RealWorld Blog API 运行中", "status": "ok"}


@router.get("/ping")
async def ping():
    """Ping 端点 — 只证明"进程还活着"，不反映依赖状态"""
    return {"ping": "pong"}


@router.get("/health")
async def health(
    request: Request,
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    健康检查 — **真的去 ping 数据库和 Redis**，而不是无脑返回 pong

    区别在哪：
    - /ping       只说明进程活着（liveness）
    - /health     说明依赖可用（readiness）—— 依赖挂了返回 503，
                  编排系统（Docker / K8s）才知道该重启它
    """
    checks: dict = {}

    # 数据库：连接池存在 + 能执行一条最轻的 SQL
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        checks["database"] = "down"
    else:
        try:
            await pool.fetchval("SELECT 1")
            checks["database"] = "up"
        except Exception:
            checks["database"] = "down"

    # Redis
    try:
        await redis_client.ping()
        checks["redis"] = "up"
    except Exception:
        checks["redis"] = "down"

    healthy = all(value == "up" for value in checks.values())

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK if healthy
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "ok" if healthy else "degraded",
            "checks": checks,
        },
    )


@router.get("/slow")
async def slow_endpoint():
    """故意慢的端点 — 测试耗时统计"""
    await asyncio.sleep(2)
    return {"message": "这条请求很慢"}


@router.get("/db-test")
async def db_test(conn: asyncpg.Connection = Depends(get_connection_from_pool)):
    """测试数据库连接"""
    version = await conn.fetchval("SELECT version()")
    return {"postgres_version": version}


@router.get("/repo-test")
async def repo_test(
    repo: UsersRepository = Depends(get_repository(UsersRepository)),
):
    """测试 Repository 依赖注入"""
    return {
        "repo_type": type(repo).__name__,
        "has_connection": repo.connection is not None,
    }


@router.get("/me")
async def me(
    current_user: UserInDB = Depends(get_current_user_authorizer()),
):
    """需要认证的端点 — 测试认证依赖链"""
    return {
        "username": current_user.username,
        "email": current_user.email,
        "bio": current_user.bio,
    }


@router.get("/required-auth")
async def required_auth(
    user: UserInDB = Depends(get_current_user_authorizer(required=True)),
):
    """必须认证"""
    return {"username": user.username, "message": "你是认证用户"}


@router.get("/optional-auth")
async def optional_auth(
    user: Optional[UserInDB] = Depends(get_current_user_authorizer(required=False)),
):
    """可选认证"""
    if user:
        return {"username": user.username, "message": "已登录"}
    return {"username": None, "message": "匿名访客"}