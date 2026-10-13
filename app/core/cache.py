import json
from typing import Optional, Any, Callable
from functools import wraps
import redis.asyncio as redis
from loguru import logger
from app.core.dependencies import get_redis


class ArticleCache:
    """文章缓存管理器"""

    # 缓存 key 前缀
    # ⚠️ PREFIX 必须和 LIST_PREFIX / DETAIL_PREFIX 同源（都是 "articles"）——
    #    invalidate_all_articles 用 scan_iter(match=f"{PREFIX}:*") 扫的就是它。
    #    曾经这里写的是 "article"（少个 s），导致 article:* 只匹配到
    #    article:views:*，文章缓存一个都删不掉 —— 函数名和实际行为正好相反。
    PREFIX = "articles"
    LIST_PREFIX = "articles:list"
    DETAIL_PREFIX = "articles:detail"

    # 缓存过期时间（秒）
    LIST_TTL = 300  # 列表缓存 5 分钟
    DETAIL_TTL = 600  # 详情缓存 10 分钟

    # ★★ 新增：空值哨兵 —— 用来"缓存一个确定为空的结果"，防缓存穿透
    #    用一个不合法 JSON 的字符串，读的时候先判断它，避免和真实数据撞车
    NULL_SENTINEL = "__NULL__"
    # ★★ 空值的 TTL 要短：它只是个"挡箭牌"，
    #    万一这期间数据真的出现了，短 TTL 能加快自愈
    NULL_TTL = 60

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _list_cache_key(
        self,
        skip: int,
        limit: int,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        favorited: Optional[str] = None,
    ) -> str:
        """
        构建文章列表缓存 key

        ⚠️ 读和写必须用**同一个**构造函数，否则会出现
        "写得进去、读不出来"的静默 bug（不报错，但命中率永远是 0）
        """
        key = f"{self.LIST_PREFIX}:{skip}:{limit}"
        if tag:
            key += f":tag:{tag}"
        if author:
            key += f":author:{author}"
        if favorited:
            key += f":favorited:{favorited}"
        return key

    async def get_article_list(
        self,
        skip: int = 0,
        limit: int = 20,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        favorited: Optional[str] = None,
    ) -> Optional[list]:
        """
        获取文章列表缓存

        返回值有三种含义，调用方必须分清：
            None  → 缓存未命中，**请去查数据库**
            []    → 命中了"空值哨兵"，说明数据库确定是空的，**不要再查库**
            [...] → 命中了真实数据
        """
        cache_key = self._list_cache_key(skip, limit, tag, author, favorited)

        try:
            cached = await self.redis.get(cache_key)

            if cached is None:
                logger.info(f"❌ 缓存未命中: {cache_key}")
                return None

            if cached == self.NULL_SENTINEL:
                # ★ 空值缓存命中：直接告诉调用方"结果就是空的"，不要去查库
                logger.info(f"🕳️ 空值命中（防穿透）: {cache_key}")
                return []

            logger.info(f"✅ 缓存命中: {cache_key}")
            return json.loads(cached)

        except Exception as e:
            # ⚠️ 缓存出问题不能让业务挂掉 —— 降级成"未命中"，去查库
            logger.error(f"获取缓存失败，降级为查库: {e}")
            return None


    async def set_article_list(
        self,
        articles: list,
        skip: int = 0,
        limit: int = 20,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        favorited: Optional[str] = None,
    ) -> bool:
        """设置文章列表缓存（空结果写哨兵 + 短 TTL）"""
        cache_key = self._list_cache_key(skip, limit, tag, author, favorited)

        try:
            if not articles:
                # ★★ 核心改动：空结果不写"空数组"，写哨兵 + 短 TTL
                await self.redis.setex(
                    cache_key,
                    self.NULL_TTL,
                    self.NULL_SENTINEL,
                )
                logger.info(f"🕳️ 空值缓存已设置: {cache_key} (TTL: {self.NULL_TTL}s)")
                return True

            await self.redis.setex(
                cache_key,
                self.LIST_TTL,
                json.dumps(articles, ensure_ascii=False, default=str),
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


    async def invalidate_all_articles(self) -> int:
        """使所有文章缓存失效（列表 + 详情）

        返回实际删除的 key 数量。
        注意：这个数字要打日志 —— 之前 prefix 写错时它一直是 0，
        但日志写的是"已失效"，把 bug 藏了很久。
        """
        try:
            keys = []
            async for key in self.redis.scan_iter(match=f"{self.PREFIX}:*"):
                keys.append(key)

            if keys:
                await self.redis.delete(*keys)

            logger.info(f"🗑️ 文章缓存已失效: {len(keys)} 个 key")
            return len(keys)
        except Exception as e:
            logger.error(f"缓存失效失败: {e}")
            return 0


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