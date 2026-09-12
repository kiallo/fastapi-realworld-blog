from fastapi import APIRouter, Depends
import redis.asyncio as redis
from app.core.dependencies import get_redis
from loguru import logger

router = APIRouter()


@router.get("/stats")
async def cache_stats(redis_client: redis.Redis = Depends(get_redis)):
    """
    获取缓存统计信息
    """
    try:
        # 获取 Redis INFO
        info = await redis_client.info()
        
        # 获取内存使用情况
        memory_used = info.get('used_memory_human', 'N/A')
        memory_peak = info.get('used_memory_peak_human', 'N/A')
        
        # 获取键空间信息
        keyspace = info.get('db0', {})
        keys_count = keyspace.get('keys', 0) if isinstance(keyspace, dict) else 0
        
        # 获取命中率
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        hit_rate = hits / (hits + misses) * 100 if (hits + misses) > 0 else 0
        
        # 获取文章相关缓存数量
        article_keys = []
        async for key in redis_client.scan_iter(match="article*"):
            article_keys.append(key)
        
        return {
            "memory": {
                "used": memory_used,
                "peak": memory_peak
            },
            "keys": {
                "total": keys_count,
                "articles": len(article_keys)
            },
            "performance": {
                "hits": hits,
                "misses": misses,
                "hit_rate": f"{hit_rate:.2f}%"
            }
        }
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        return {"error": str(e)}


@router.delete("/clear")
async def clear_all_cache(redis_client: redis.Redis = Depends(get_redis)):
    """
    清除所有缓存（谨慎使用）
    """
    try:
        await redis_client.flushdb()
        logger.warning("⚠️ 所有缓存已清除")
        return {"message": "所有缓存已清除"}
    except Exception as e:
        logger.error(f"清除缓存失败: {e}")
        return {"error": str(e)}