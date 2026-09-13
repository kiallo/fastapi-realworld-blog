from typing import AsyncGenerator
from loguru import logger
import redis.asyncio as redis
from fastapi import Depends
from app.core.config import get_app_settings
from app.services.token_storage import TokenStorage


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
                password=self.settings.redis_password,
                decode_responses=True,
                # 连接池配置
                max_connections=20,
                retry_on_timeout=True
            )
        
        try:
            yield self._redis_client
        except redis.ConnectionError as e:
            logger.error(f"Redis 连接错误: {e}")
            raise
        finally:
            pass  # 连接池会管理连接


# 创建全局实例
redis_dependency = RedisDependency()

# 依赖函数
async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """获取 Redis 连接的依赖函数"""
    async for client in redis_dependency.get_redis_client():
        yield client


async def get_token_storage(
    redis_client: redis.Redis = Depends(get_redis),
) -> AsyncGenerator["TokenStorage", None]:
    """
    获取 TokenStorage 的依赖函数

    用法：
        @router.post("/logout")
        async def logout(token_storage: TokenStorage = Depends(get_token_storage)):
            ...
    """
    from app.services.token_storage import TokenStorage
    yield TokenStorage(redis_client)