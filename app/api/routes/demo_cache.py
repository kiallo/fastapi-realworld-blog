"""
第一课练习：Redis 缓存演示路由
仅供学习，不影响项目原有的 articles 接口
"""
from fastapi import APIRouter, Depends
import redis.asyncio as redis
import json
from app.core.dependencies import get_redis

router = APIRouter()


@router.get("/demo/articles")
async def list_articles_cached(
    skip: int = 0,
    limit: int = 100,
    redis_client: redis.Redis = Depends(get_redis),
):
    # 尝试从缓存获取
    cache_key = f"demo:articles:list:{skip}:{limit}"
    cached = await redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # 模拟数据（实际项目中这里会查数据库）
    articles = [
        {"id": 1, "title": "FastAPI入门", "content": "FastAPI是一个现代、快速Web框架"},
        {"id": 2, "title": "Redis缓存", "content": "Redis是一个内存数据结构存储"},
        {"id": 3, "title": "依赖注入", "content": "FastAPI的依赖注入系统非常强大"},
    ]

    # 分页处理
    paginated_articles = articles[skip : skip + limit]

    # 存储到缓存（5分钟过期）
    await redis_client.setex(
        cache_key,
        300,  # 5分钟
        json.dumps(paginated_articles),
    )

    return paginated_articles
