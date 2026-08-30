import asyncpg


class BaseRepository:
    """
    Repository 基类

    职责：
    1. 持有数据库连接
    2. 提供子类统一的连接访问方式
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    @property
    def connection(self) -> asyncpg.Connection:
        return self._conn