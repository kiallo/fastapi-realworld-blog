"""Fake asyncpg pool for testing without a real database."""
from unittest.mock import AsyncMock, MagicMock


class FakeAsyncPGPool:
    """
    模拟 asyncpg 连接池

    用于测试时替代真实的 PostgreSQL 连接池
    所有数据库操作都返回 mock 对象
    """

    def __init__(self):
        self._conn = MagicMock()
        self._conn.fetch = AsyncMock(return_value=[])
        self._conn.fetchrow = AsyncMock(return_value=None)
        self._conn.execute = AsyncMock(return_value="OK")
        self._conn.transaction = MagicMock()

    async def acquire(self):
        return self._conn

    async def release(self, conn):
        pass

    async def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConnectionContextManager:
    """模拟 async with pool.acquire() as conn 的上下文管理器"""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass
