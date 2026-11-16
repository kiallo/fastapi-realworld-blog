"""文章缓存测试：key 命名、TTL、空值哨兵、批量失效。

全部用 fakeredis 内存实例，不连真实 Redis。
decode_responses=True 必须和 app/core/dependencies.py 里的建连参数一致——
否则 get() 返回 bytes，ArticleCache 里 `cached == NULL_SENTINEL` 的字符串
比较永远为 False，哨兵逻辑会「假通过」。
"""

import fakeredis.aioredis
import pytest

from app.core.cache import ArticleCache


@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()


@pytest.fixture
def cache(redis_client):
    return ArticleCache(redis_client)


class TestListCacheKey:
    def test_key_without_filters(self, cache):
        assert cache._list_cache_key(0, 20) == "articles:list:0:20"

    def test_key_includes_tag(self, cache):
        assert cache._list_cache_key(0, 20, tag="python") == "articles:list:0:20:tag:python"

    def test_key_orders_filters_consistently(self, cache):
        """读写必须用同一个构造函数；顺序错位会出现「写得进读不出」的静默 bug"""
        key = cache._list_cache_key(0, 20, tag="t", author="a", favorited="f")
        assert key == "articles:list:0:20:tag:t:author:a:favorited:f"


class TestListCacheReadWrite:
    async def test_miss_returns_none(self, cache):
        assert await cache.get_article_list(0, 20) is None

    async def test_write_then_read_roundtrip(self, cache):
        await cache.set_article_list([{"slug": "a"}], 0, 20)
        assert await cache.get_article_list(0, 20) == [{"slug": "a"}]

    async def test_list_ttl_is_300(self, cache, redis_client):
        await cache.set_article_list([{"slug": "a"}], 0, 20)
        ttl = await redis_client.ttl("articles:list:0:20")
        assert 0 < ttl <= 300

    async def test_empty_list_writes_sentinel_with_short_ttl(self, cache, redis_client):
        """空结果不写 []，写哨兵 + 60 秒短 TTL，防缓存穿透"""
        await cache.set_article_list([], 0, 20)
        assert await redis_client.get("articles:list:0:20") == cache.NULL_SENTINEL
        ttl = await redis_client.ttl("articles:list:0:20")
        assert 0 < ttl <= 60

    async def test_sentinel_reads_back_as_empty_list(self, cache):
        """哨兵命中要返回 []（确定为空，别再查库），不是 None"""
        await cache.set_article_list([], 0, 20)
        assert await cache.get_article_list(0, 20) == []

    async def test_corrupted_value_degrades_to_miss(self, cache, redis_client):
        """缓存坏了不能拖垮业务，降级成「未命中」去查库"""
        await redis_client.set("articles:list:0:20", "not-a-json")
        assert await cache.get_article_list(0, 20) is None


class TestSummaryCache:
    async def test_roundtrip_and_ttl(self, cache, redis_client):
        payload = {"summary": {"summary": "x"}, "model": "test-model"}
        await cache.set_article_summary(1, payload)

        assert await cache.get_article_summary(1) == payload
        ttl = await redis_client.ttl("articles:summary:1")
        assert 0 < ttl <= 3600

    async def test_missing_returns_none(self, cache):
        assert await cache.get_article_summary(999) is None


class TestInvalidateAll:
    async def test_deletes_list_detail_and_summary_keys(self, cache):
        await cache.set_article_list([{"slug": "a"}], 0, 20)
        await cache.set_article_detail(1, {"slug": "a"})
        await cache.set_article_summary(1, {"model": "m"})

        assert await cache.invalidate_all_articles() == 3
        assert await cache.get_article_list(0, 20) is None
        assert await cache.get_article_detail(1) is None
