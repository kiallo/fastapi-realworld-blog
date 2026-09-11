import json
from typing import Any, Optional
import redis.asyncio as redis
from loguru import logger

class RedisUtils:
    """Redis 工具类"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def cache_set(
        self, 
        key: str, 
        value: Any, 
        expire: int = 300  # 默认5分钟
    ) -> bool:
        """设置缓存"""
        try:
            await self.redis.setex(
                key,
                expire,
                json.dumps(value, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def cache_delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def cache_delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的缓存"""
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0
    
    async def increment_counter(self, key: str, amount: int = 1) -> int:
        """自增计数器"""
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Increment counter error: {e}")
            return 0
    
    async def add_to_list(self, key: str, value: Any, max_length: int = 100):
        """添加到列表（保持最大长度）"""
        try:
            await self.redis.lpush(key, json.dumps(value, ensure_ascii=False))
            await self.redis.ltrim(key, 0, max_length - 1)
        except Exception as e:
            logger.error(f"Add to list error: {e}")
    
    async def get_list(self, key: str, start: int = 0, end: int = -1) -> list:
        """获取列表"""
        try:
            items = await self.redis.lrange(key, start, end)
            return [json.loads(item) for item in items]
        except Exception as e:
            logger.error(f"Get list error: {e}")
            return []