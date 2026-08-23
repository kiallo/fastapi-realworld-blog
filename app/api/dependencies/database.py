from typing import AsyncGenerator
import asyncpg
from fastapi import Request


async def get_connection_from_pool(
    request: Request,
) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    从连接池获取一个连接，请求结束后自动归还

    用法：在路由函数中声明
        async def my_endpoint(conn = Depends(get_connection_from_pool)):
            row = await conn.fetchrow("SELECT ...")
    """
    pool: asyncpg.Pool = request.app.state.pool

    async with pool.acquire() as connection:
        yield connection # type: ignore
    # async with 结束后自动归还连接