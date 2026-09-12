"""
Redis 缓存演示路由
仅供学习，不影响项目原有的 articles 接口
"""
from typing import Optional
from loguru import logger
from fastapi import APIRouter, Depends
import redis.asyncio as redis
import json
from app.core.cache import ArticleCache
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


@router.get("/", response_model=dict)
async def list_articles(
    skip: int = 0,
    limit: int = 20,
    tag: Optional[str] = None,
    author: Optional[str] = None,
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    获取文章列表（带缓存）
    
    - 先查询 Redis 缓存
    - 缓存未命中时查询数据库
    - 将结果写入缓存
    """
    cache = ArticleCache(redis_client)

    # 1. 尝试从缓存获取
    cached_articles = await cache.get_article_list(
        skip=skip, 
        limit=limit, 
        tag=tag, 
        author=author
    )

    if cached_articles:
        return {
            "articles": cached_articles,
            "articles_count": len(cached_articles),
            "source": "cache"
        }

    # 2. 缓存未命中，查询数据库
    logger.info("📊 查询数据库获取文章列表")
    
    # 这里替换为你的实际数据库查询
    # articles = await db.query(Article).offset(skip).limit(limit).all()

    # 模拟数据库查询结果
    articles = [
        {
            "id": 1,
            "title": "FastAPI入门教程",
            "description": "学习FastAPI的基础知识",
            "body": "FastAPI是一个现代、快速的Web框架...",
            "tagList": ["Python", "FastAPI"],
            "createdAt": "2024-01-01T00:00:00",
            "favoritesCount": 10
        },
        {
            "id": 2,
            "title": "Redis缓存实践",
            "description": "如何使用Redis优化应用性能",
            "body": "Redis是一个高性能的内存数据库...",
            "tagList": ["Redis", "缓存"],
            "createdAt": "2024-01-02T00:00:00",
            "favoritesCount": 20
        }
    ]

    # 3. 将结果写入缓存
    await cache.set_article_list(
        articles=articles,
        skip=skip,
        limit=limit,
        tag=tag,
        author=author
    )

    return {
        "articles": articles,
        "articles_count": len(articles),
        "source": "database"
    }


@router.get("/{article_id}", response_model=dict)
async def get_article(
    article_id: int,
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    获取文章详情（带缓存）
    """
    cache = ArticleCache(redis_client)
    
    # 1. 尝试从缓存获取
    cached_article = await cache.get_article_detail(article_id)
    
    if cached_article:
        # 增加浏览量（异步，不影响响应）
        await cache.increment_view_count(article_id)
        return {
            "article": cached_article,
            "source": "cache"
        }
    
    # 2. 缓存未命中，查询数据库
    logger.info(f"📊 查询数据库获取文章详情: {article_id}")
    
    # 模拟数据库查询
    article = {
        "id": article_id,
        "title": "示例文章",
        "description": "这是一篇示例文章",
        "body": "文章内容...",
        "tagList": ["示例"],
        "createdAt": "2024-01-01T00:00:00",
        "favoritesCount": 5
    }
    
    # 3. 写入缓存
    await cache.set_article_detail(article_id, article)
    
    # 增加浏览量
    await cache.increment_view_count(article_id)
    
    return {
        "article": article,
        "source": "database"
    }


@router.post("/", response_model=dict)
async def create_article(
    article_data: dict,
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    创建文章（清除相关缓存）
    """
    # 1. 保存到数据库
    logger.info("📝 创建新文章")
    
    # 模拟创建文章
    new_article = {
        "id": 3,
        **article_data,
        "createdAt": "2024-01-03T00:00:00",
        "favoritesCount": 0
    }
    
    # 2. 清除列表缓存（因为新增了文章）
    cache = ArticleCache(redis_client)
    await cache.invalidate_all_articles()
    
    return {
        "article": new_article,
        "message": "文章创建成功"
    }


@router.put("/{article_id}", response_model=dict)
async def update_article(
    article_id: int,
    article_data: dict,
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    更新文章（清除相关缓存）
    """
    # 1. 更新数据库
    logger.info(f"📝 更新文章: {article_id}")
    
    # 模拟更新
    updated_article = {
        "id": article_id,
        **article_data,
        "updatedAt": "2024-01-03T12:00:00"
    }
    
    # 2. 清除该文章的缓存
    cache = ArticleCache(redis_client)
    await cache.invalidate_article(article_id)
    
    return {
        "article": updated_article,
        "message": "文章更新成功"
    }


@router.delete("/{article_id}")
async def delete_article(
    article_id: int,
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    删除文章（清除相关缓存）
    """
    # 1. 删除数据库记录
    logger.info(f"🗑️ 删除文章: {article_id}")
    
    # 2. 清除缓存
    cache = ArticleCache(redis_client)
    await cache.invalidate_article(article_id)
    
    return {
        "message": "文章删除成功"
    }


@router.get("/{article_id}/views")
async def get_article_views(
    article_id: int,
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    获取文章浏览量
    """
    cache = ArticleCache(redis_client)
    views = await cache.get_view_count(article_id)
    
    return {
        "article_id": article_id,
        "views": views
    }