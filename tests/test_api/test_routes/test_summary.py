"""摘要接口的 8 个分支。

GET  /articles/{slug}/summary        404 无缓存 / 200 有缓存
POST /articles/{slug}/summary        403 非作者 / 202 缓存命中 / 202 建任务
                                     503 LLM 未配置
GET  /articles/{slug}/summary/tasks/{task_id}   200 状态 / 404 不存在

⚠️ 三个容易踩的点：

1) articles_summary.py 里是 `get_summary_service(request)` 直接调用，
   不是 Depends，所以 dependency_overrides 对它无效，
   必须改 `app.state.summary_service`。

2) 这里自定义了 client fixture（不跑 lifespan），
   因为 lifespan 会把 state.summary_service 重设为 None，
   而且会真实连 PostgreSQL，8 条测试要多花 6 秒。

3) 第 29 课把 POST 从「同步返回 200」改成了「202 + 任务」，
   原来断言 200/409/504 的四条已迁移：409 改成"连点只调一次模型"，
   504 改成"任务落 failed"。
"""

import asyncio
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
    service.generate = AsyncMock(return_value=(content, {"input_tokens": 1, "output_tokens": 1}))
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


async def _wait_task_done(client, task_id: str, timeout: float = 5.0) -> str:
    """轮询到终态，返回最终 status。

    固定 sleep 在慢机器上会 flaky；这里按时间上限轮询，
    最多等 timeout 秒，超时直接失败（而不是返回中间状态）。
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    status = "pending"
    while loop.time() < deadline:
        resp = await client.get(f"/articles/{SLUG}/summary/tasks/{task_id}")
        status = resp.json()["status"]
        if status in ("succeeded", "failed"):
            return status
        await asyncio.sleep(0.02)
    raise AssertionError(f"任务 {task_id} 超时未终态，最后状态 {status}")


async def test_post_returns_cache_without_calling_llm(
    client, setup_api, fake_redis, article, fake_service
):
    """已有缓存：不建任务、不调模型，直接返回 succeeded"""
    await ArticleCache(fake_redis).set_article_summary(article.id, CACHED_PAYLOAD)

    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["taskId"] == f"cached-{article.id}"
    assert body["summary"]["summary"] == CACHED_PAYLOAD["summary"]["summary"]
    fake_service.generate.assert_not_awaited()


async def test_post_generates_and_writes_cache(client, setup_api, fake_redis, article):
    """首次提交：202 + 后台跑完 + 缓存落库"""
    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 202
    task_id = response.json()["taskId"]

    status = await _wait_task_done(client, task_id)
    assert status == "succeeded"

    cached = await ArticleCache(fake_redis).get_article_summary(article.id)
    assert cached is not None, "生成后必须落缓存，否则下次还得再花一次钱"


async def test_concurrent_submit_calls_model_once(client, setup_api, fake_service):
    """连点两次：模型只被调用一次（钱只花一次）——原来 409 那条的继任者"""
    original = fake_service.generate
    calls = 0

    async def _slow_generate(**kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.2)  # 制造"正在跑"的窗口
        return await original(**kwargs)

    fake_service.generate = _slow_generate

    first = await client.post(f"/articles/{SLUG}/summary")
    second = await client.post(f"/articles/{SLUG}/summary")

    assert first.json()["taskId"] == second.json()["taskId"]

    await _wait_task_done(client, first.json()["taskId"])
    assert calls == 1, "连点两次只该调一次模型，否则钱要花两次"


async def test_post_returns_503_when_llm_not_configured(client, setup_api):
    """把 state 里的服务摘掉，模拟「没配 LLM_API_KEY」的启动状态"""
    setup_api.state.summary_service = None

    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 503
    assert response.json()["errors"]["body"][0] == "LLM 未配置，摘要功能不可用"


async def test_post_timeout_marks_task_failed(client, setup_api, fake_service):
    """超时不再返回 504，而是任务落到 failed（执行器还会重试一次，约 1 秒）"""
    fake_service.generate = AsyncMock(side_effect=SummaryTimeoutError("超时"))

    response = await client.post(f"/articles/{SLUG}/summary")

    assert response.status_code == 202

    task_id = response.json()["taskId"]
    status = await _wait_task_done(client, task_id)
    assert status == "failed"

    poll = await client.get(f"/articles/{SLUG}/summary/tasks/{task_id}")
    assert "超时" in poll.json()["error"]
