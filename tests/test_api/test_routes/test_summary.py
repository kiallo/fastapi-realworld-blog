"""摘要接口的 8 个分支。

GET  /articles/{slug}/summary   404 无缓存 / 200 有缓存
POST /articles/{slug}/summary   403 非作者 / 200 缓存命中 / 200 首次生成
                               409 锁被占 / 503 LLM 未配置 / 504 超时

⚠️ 两个容易踩的点：

1) articles_summary.py 里是 `get_summary_service(request)` 直接调用，
   不是 Depends，所以 dependency_overrides 对它无效，
   必须改 `app.state.summary_service`。

2) 这里自定义了 client fixture（不跑 lifespan），
   因为 lifespan 会把 state.summary_service 重设为 None，
   而且会真实连 PostgreSQL，8 条测试要多花 6 秒。
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.articles import get_article_by_slug_from_path
from app.api.dependencies.authentication import _get_current_user
from app.core.cache import ArticleCache
from app.core.dependencies import get_redis
from app.main import get_application
from app.models.domain.articles import Article
from app.models.domain.profiles import Profile
from app.models.domain.users import UserInDB
from app.services.summary import SummaryTimeoutError

SLUG = "test-slug"

CACHED_PAYLOAD = {
    "summary": {
        "summary": "这是一段已经生成好的摘要内容，长度足够通过校验。",
        "keywords": ["python", "fastapi"],
        "difficulty": "beginner",
    },
    "model": "cached-model",
    "usage": {"input_tokens": 1, "output_tokens": 1},
}


@pytest.fixture
def summary_app():
    """独立 app 实例，不跑 lifespan：不连 PostgreSQL、不建连接池"""
    return get_application()


@pytest.fixture
async def client(summary_app):
    """覆盖 conftest 里那个跑 lifespan 的 client，让这 8 条测试跑得飞快"""
    async with AsyncClient(
        transport=ASGITransport(app=summary_app),
        base_url="http://testserver/api",
    ) as c:
        yield c


@pytest.fixture
def article():
    return Article(
        id=1,
        slug=SLUG,
        title="测试文章",
        description="d",
        body="body content",
        author=Profile(username="author"),
        tags=[],
        favorited=False,
        favorites_count=0,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def author_user():
    return UserInDB(
        id=1,
        username="author",
        email="author@example.com",
        salt="s",
        hashed_password="h",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def other_user():
    return UserInDB(
        id=2,
        username="someone-else",
        email="other@example.com",
        salt="s",
        hashed_password="h",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )


@pytest.fixture
async def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def fake_service():
    service = MagicMock()
    service.model = "test-model"
    content = MagicMock()
    content.model_dump.return_value = CACHED_PAYLOAD["summary"]
    service.generate = AsyncMock(
        return_value=(content, {"input_tokens": 1, "output_tokens": 1})
    )
    return service


@pytest.fixture
def setup_api(summary_app, article, author_user, fake_redis, fake_service):
    """把文章、当前用户、Redis、LLM 服务全部换成假对象"""
    summary_app.dependency_overrides[get_article_by_slug_from_path] = lambda: article
    summary_app.dependency_overrides[_get_current_user] = lambda: author_user
    summary_app.dependency_overrides[get_redis] = lambda: fake_redis
    summary_app.state.summary_service = fake_service

    yield summary_app

    summary_app.dependency_overrides.clear()
    summary_app.state.summary_service = None


async def test_get_returns_404_when_no_cache(client, setup_api):
    response = await client.get(f"/articles/{SLUG}/summary")

    assert response.status_code == 404
    assert response.json()["errors"]["body"][0] == "这篇文章还没有生成摘要"


async def test_get_returns_cached_summary(client, setup_api, fake_redis, article):
    await ArticleCache(fake_redis).set_article_summary(article.id, CACHED_PAYLOAD)

    response = await client.get(f"/articles/{SLUG}/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is True
    assert body["model"] == "cached-model"
    assert body["summary"]["difficulty"] == "beginner"


async def test_post_forbidden_for_non_author(client, setup_api, other_user):
    setup_api.dependency_overrides[_get_current_user] = lambda: other_user

    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 403
    assert response.json()["errors"]["body"][0] == "只有作者可以生成摘要"


async def test_post_returns_cache_without_calling_llm(
    client, setup_api, fake_redis, article, fake_service
):
    """已有缓存时直接返回：不调模型、不加锁、不花钱"""
    await ArticleCache(fake_redis).set_article_summary(article.id, CACHED_PAYLOAD)

    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 200
    assert response.json()["cached"] is True
    fake_service.generate.assert_not_awaited()


async def test_post_generates_and_writes_cache(client, setup_api, fake_redis, article):
    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is False
    assert body["model"] == "test-model"

    cached = await ArticleCache(fake_redis).get_article_summary(article.id)
    assert cached is not None, "生成后必须落缓存，否则下次还得再花一次钱"


async def test_post_returns_409_when_lock_held(
    client, setup_api, fake_redis, article, fake_service
):
    """并发请求拿不到锁 → 409，不排队、不重复调模型"""
    await fake_redis.set(f"summary:lock:{article.id}", "1", ex=60)

    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 409
    fake_service.generate.assert_not_awaited()


async def test_post_returns_503_when_llm_not_configured(client, setup_api):
    """把 state 里的服务摘掉，模拟「没配 LLM_API_KEY」的启动状态"""
    setup_api.state.summary_service = None

    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 503
    assert response.json()["errors"]["body"][0] == "LLM 未配置，摘要功能不可用"


async def test_post_returns_504_on_timeout(client, setup_api, fake_service):
    fake_service.generate = AsyncMock(side_effect=SummaryTimeoutError("超时"))

    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 504
    assert "超时" in response.json()["errors"]["body"][0]
