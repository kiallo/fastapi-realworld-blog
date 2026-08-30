from typing import AsyncGenerator, Type, Callable
import asyncpg
from fastapi import Request, Depends
from app.db.repositories.base import BaseRepository


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


def get_repository(repo_type: Type[BaseRepository]) -> Callable:
    """
    泛型 Repository 依赖注入工厂

    工作原理（高阶函数 + 闭包）：
    1. 接收一个 Repository 类（如 UsersRepository）
    2. 返回一个 _get_repo 函数（闭包，捕获了 repo_type）
    3. FastAPI 调用 Depends 时，执行 _get_repo，传入连接，实例化 Repository

    使用方式：
        repo: UsersRepository = Depends(get_repository(UsersRepository))
    """

    def _get_repo(
        conn: asyncpg.Connection = Depends(get_connection_from_pool),
    ) -> BaseRepository:
        return repo_type(conn)

    return _get_repo