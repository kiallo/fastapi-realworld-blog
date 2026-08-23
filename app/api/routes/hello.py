from fastapi import APIRouter, Depends
import asyncio
import asyncpg
from app.api.dependencies.database import get_connection_from_pool

router = APIRouter()


@router.get("/")
async def root():
    """根路径 - 健康检查"""
    return {"message": "RealWorld Blog API 运行中", "status": "ok"}


@router.get("/ping")
async def ping():
    """Ping 端点 — 负载均衡器常用"""
    return {"ping": "pong"}


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