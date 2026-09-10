from typing import AsyncGenerator
import redis.asyncio as redis
from app.core.config import get_app_settings


class RedisDependency:
    """Redis 连接依赖"""

    def __init__(self):
        self.settings = get_app_settings()
        self._redis_client = None

    async def get_redis_client(self) -> AsyncGenerator[redis.Redis, None]:
        """获取 Redis 客户端的依赖函数"""
        if self._redis_client is None:
            self._redis_client = redis.Redis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                decode_responses=True
            )
        
        try:
            yield self._redis_client
        finally:
            # 注意：这里不关闭连接，因为连接池会管理
            pass


# 创建全局实例
redis_dependency = RedisDependency()

# 依赖函数
async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """获取 Redis 连接的依赖函数"""
    async for client in redis_dependency.get_redis_client():
        yield client