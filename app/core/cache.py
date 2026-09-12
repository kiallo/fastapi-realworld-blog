import json
from typing import Optional, Any, Callable
from functools import wraps
import redis.asyncio as redis
from loguru import logger
from app.core.dependencies import get_redis


class ArticleCache:
    """文章缓存管理器"""

    # 缓存 key 前缀
    PREFIX = "article"
    LIST_PREFIX = "articles:list"
    DETAIL_PREFIX = "articles:detail"

    # 缓存过期时间（秒）
    LIST_TTL = 300  # 列表缓存 5 分钟
    DETAIL_TTL = 600  # 详情缓存 10 分钟

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client


    async def get_article_list(
        self, 
        skip: int = 0, 
        limit: int = 20,
        tag: Optional[str] = None,
        author: Optional[str] = None
    ) -> Optional[list]:
        """获取文章列表缓存"""
        # 构建缓存 key
        cache_key = f"{self.LIST_PREFIX}:{skip}:{limit}"
        if tag:
            cache_key += f":tag:{tag}"
        if author:
            cache_key += f":author:{author}"

        try:
            cached = await self.redis.get(cache_key)
            if cached:
                logger.info(f"✅ 缓存命中: {cache_key}")
                return json.loads(cached)
            
            logger.info(f"❌ 缓存未命中: {cache_key}")
            return None
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            return None


    async def set_article_list(
        self,
        articles: list,
        skip: int = 0,
        limit: int = 20,
        tag: Optional[str] = None,
        author: Optional[str] = None
    ) -> bool:
        """设置文章列表缓存"""
        cache_key = f"{self.LIST_PREFIX}:{skip}:{limit}"
        if tag:
            cache_key += f":tag:{tag}"
        if author:
            cache_key += f":author:{author}"

        try:
            await self.redis.setex(
                cache_key,
                self.LIST_TTL,
                json.dumps(articles, ensure_ascii=False, default=str)
            )
            logger.info(f"💾 缓存已设置: {cache_key} (TTL: {self.LIST_TTL}s)")
            return True
        except Exception as e:
            logger.error(f"设置缓存失败: {e}")
            return False


    async def get_article_detail(self, article_id: int) -> Optional[dict]:
        """获取文章详情缓存"""
        cache_key = f"{self.DETAIL_PREFIX}:{article_id}"
        
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                logger.info(f"✅ 缓存命中: {cache_key}")
                return json.loads(cached)
            
            logger.info(f"❌ 缓存未命中: {cache_key}")
            return None
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            return None


    async def set_article_detail(
        self, 
        article_id: int, 
        article_data: dict
    ) -> bool:
        """设置文章详情缓存"""
        cache_key = f"{self.DETAIL_PREFIX}:{article_id}"
        
        try:
            await self.redis.setex(
                cache_key,
                self.DETAIL_TTL,
                json.dumps(article_data, ensure_ascii=False, default=str)
            )
            logger.info(f"💾 缓存已设置: {cache_key} (TTL: {self.DETAIL_TTL}s)")
            return True
        except Exception as e:
            logger.error(f"设置缓存失败: {e}")
            return False


    async def invalidate_article(self, article_id: int):
        """使文章缓存失效"""
        try:
            # 删除文章详情缓存
            detail_key = f"{self.DETAIL_PREFIX}:{article_id}"
            await self.redis.delete(detail_key)

            logger.info(f"🗑️ 缓存已失效: article_id={article_id}")
        except Exception as e:
            logger.error(f"缓存失效失败: {e}")


    async def invalidate_all_articles(self):
        """使所有文章缓存失效"""
        try:
            keys = []
            async for key in self.redis.scan_iter(match=f"{self.PREFIX}:*"):
                keys.append(key)
            
            if keys:
                await self.redis.delete(*keys)
            
            logger.info(f"🗑️ 所有文章缓存已失效")
        except Exception as e:
            logger.error(f"缓存失效失败: {e}")


    async def increment_view_count(self, article_id: int) -> int:
        """增加文章浏览量"""
        try:
            count = await self.redis.incr(f"article:views:{article_id}")
            logger.info(f"👁️ 文章浏览量: article_id={article_id}, views={count}")
            return count
        except Exception as e:
            logger.error(f"增加浏览量失败: {e}")
            return 0


    async def get_view_count(self, article_id: int) -> int:
        """获取文章浏览量"""
        try:
            count = await self.redis.get(f"article:views:{article_id}")
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"获取浏览量失败: {e}")
            return 0


    def cache_key_builder(*args, **kwargs) -> str:
        """构建缓存 key"""
        parts = [str(arg) for arg in args]
        parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
        return ":".join(parts)