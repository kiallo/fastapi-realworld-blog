"""异步摘要任务的 5 个用例。

复用 test_summary.py 的思路：不跑 lifespan、fakeredis、假 service。
异步任务用"轮询到终态"等，不用固定 sleep。
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.articles import get_article_by_slug_from_path
from app.api.dependencies.authentication import _get_current_user
from app.core.dependencies import get_redis
from app.main import get_application
from app.models.domain.articles import Article
from app.models.domain.profiles import Profile
from app.models.domain.users import UserInDB
from app.services.summary import SummaryError

SLUG = "task-slug"
SUMMARY_PAYLOAD = {
    "summary": "这是一段足够长的摘要内容，用来通过 Pydantic 的最小长度校验。",
    "keywords": ["python", "fastapi"],
    "difficulty": "beginner",
}


@pytest.fixture
def task_app():
    return get_application()


@pytest.fixture
async def client(task_app):
    async with AsyncClient(
        transport=ASGITransport(app=task_app), base_url="http://testserver/api"
    ) as c:
        yield c


@pytest.fixture
def article():
    return Article(
        id=99,
        slug=SLUG,
        title="测试文章",
        description="d",
        body="body",
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
        email="a@example.com",
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
    service.model = "fake-model"
    content = MagicMock()
    content.model_dump.return_value = SUMMARY_PAYLOAD
    service.generate = AsyncMock(return_value=(content, {"input_tokens": 1, "output_tokens": 1}))
    return service


@pytest.fixture
def wired(task_app, article, author_user, fake_redis, fake_service):
    task_app.dependency_overrides[get_article_by_slug_from_path] = lambda: article
    task_app.dependency_overrides[_get_current_user] = lambda: author_user
    task_app.dependency_overrides[get_redis] = lambda: fake_redis
    task_app.state.summary_service = fake_service
    yield
    task_app.dependency_overrides.clear()


async def _wait_terminal(client: AsyncClient, task_id: str, timeout: float = 3.0) -> dict:
    """轮询到终态为止——不要用固定 sleep，机器快慢不同会 flaky。"""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        resp = await client.get(f"/articles/{SLUG}/summary/tasks/{task_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] in ("succeeded", "failed"):
            return body
        await asyncio.sleep(0.02)
    raise AssertionError(f"任务 {task_id} 在 {timeout}s 内没有进入终态")


@pytest.mark.asyncio
async def test_submit_returns_202_with_task_id(client, wired):
    """① 首次提交立刻返回 202"""
    resp = await client.post(f"/articles/{SLUG}/summary")
    assert resp.status_code == 202
    body = resp.json()
    assert body["taskId"]  # 注意：响应是 camelCase，不是 task_id
    assert body["status"] in ("pending", "running")


@pytest.mark.asyncio
async def test_second_submit_returns_same_task_id(client, wired, fake_service):
    """② 幂等：任务还在跑的时候再点一次，还是同一个任务

    ⚠️ 必须把假 service 拖慢。真实 LLM 要跑几秒，窗口是开着的；
    如果它瞬间返回，第二次请求会先命中「已有缓存」分支，拿到合成 id `cached-99`——
    那不是幂等失败，是**窗口已经关了**，测的东西变了。
    """
    original = fake_service.generate

    async def _slow_generate(**kwargs):
        await asyncio.sleep(0.3)  # 制造一个"正在跑"的窗口
        return await original(**kwargs)

    fake_service.generate = _slow_generate

    first = (await client.post(f"/articles/{SLUG}/summary")).json()
    second = (await client.post(f"/articles/{SLUG}/summary")).json()
    assert second["taskId"] == first["taskId"]

    # 收尾：等任务跑完，别留一个后台任务给下一个用例
    await _wait_terminal(client, first["taskId"])


@pytest.mark.asyncio
async def test_poll_until_succeeded(client, wired):
    """③ 轮询能拿到 succeeded 和摘要内容"""
    task = (await client.post(f"/articles/{SLUG}/summary")).json()
    final = await _wait_terminal(client, task["taskId"])
    assert final["status"] == "succeeded"
    assert final["summary"]["summary"] == SUMMARY_PAYLOAD["summary"]


@pytest.mark.asyncio
async def test_failure_marks_task_failed(client, wired, fake_service):
    """④ 服务持续失败时，任务落到 failed 并带原因"""
    fake_service.generate = AsyncMock(side_effect=SummaryError("模型挂了"))
    task = (await client.post(f"/articles/{SLUG}/summary")).json()
    final = await _wait_terminal(client, task["taskId"])
    assert final["status"] == "failed"
    assert "模型挂了" in (final["error"] or "")


@pytest.mark.asyncio
async def test_non_author_gets_403(client, task_app, wired):
    """⑤ 非作者不能提交任务（权限检查不能在改造中丢掉）"""
    other = UserInDB(
        id=2,
        username="intruder",
        email="i@example.com",
        salt="s",
        hashed_password="h",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )
    task_app.dependency_overrides[_get_current_user] = lambda: other
    resp = await client.post(f"/articles/{SLUG}/summary")
    assert resp.status_code == 403
