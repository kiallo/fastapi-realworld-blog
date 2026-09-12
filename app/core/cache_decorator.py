import json
import hashlib
from typing import Optional, Callable
from functools import wraps
import redis.asyncio as redis
from loguru import logger

def cached(
    prefix: str,
    ttl: int = 300,
    key_builder: Optional[Callable] = None
):
    """
    缓存装饰器
    
    使用示例：
    @cached(prefix="articles", ttl=600)
    async def get_articles(skip: int = 0, limit: int = 20):
        ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取 Redis 连接（需要从依赖注入获取）
            # 这里简化处理，实际项目中应通过依赖注入
            from app.core.dependencies import redis_dependency
            
            if redis_dependency._redis_client is None:
                return await func(*args, **kwargs)
            
            r = redis_dependency._redis_client
            
            # 构建缓存 key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # 默认 key 构建
                key_parts = [prefix]
                key_parts.extend([str(arg) for arg in args[1:]])  # 跳过 self
                key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
                cache_key = ":".join(key_parts)
            
            try:
                # 尝试从缓存获取
                cached_data = await r.get(cache_key)
                if cached_data:
                    logger.info(f"✅ 装饰器缓存命中: {cache_key}")
                    return json.loads(cached_data)
                
                # 执行原函数
                result = await func(*args, **kwargs)
                
                # 写入缓存
                await r.setex(
                    cache_key,
                    ttl,
                    json.dumps(result, ensure_ascii=False, default=str)
                )
                logger.info(f"💾 装饰器缓存已设置: {cache_key}")
                
                return result
                
            except Exception as e:
                logger.error(f"缓存装饰器错误: {e}")
                # 缓存出错时直接执行原函数
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def cache_invalidate(prefix: str):
    """
    缓存失效装饰器
    
    使用示例：
    @cache_invalidate(prefix="articles")
    async def update_article(article_id: int, ...):
        ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # 执行成功后清除缓存
            try:
                from app.core.dependencies import redis_dependency
                
                if redis_dependency._redis_client:
                    r = redis_dependency._redis_client
                    keys = []
                    async for key in r.scan_iter(match=f"{prefix}:*"):
                        keys.append(key)
                    
                    if keys:
                        await r.delete(*keys)
                        logger.info(f"🗑️ 缓存已失效: {prefix}:* ({len(keys)} keys)")
            except Exception as e:
                logger.error(f"缓存失效失败: {e}")
            
            return result
        
        return wrapper
    return decorator