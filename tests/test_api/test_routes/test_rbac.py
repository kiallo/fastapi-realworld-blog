"""RBAC 的五个用例 —— 对应第 28 课 3.2 的权限矩阵。

注意：注册接口不收 role，所以测试用"直接改库"的方式造管理员，
这和运维提权是同一条路径。
"""

import uuid

import asyncpg
import pytest
from httpx import AsyncClient

from app.core.config import get_app_settings


def _payload(prefix: str = "rbac") -> dict:
    suffix = uuid.uuid4().hex[:8]
    return {
        "username": f"{prefix}_{suffix}",
        "email": f"{prefix}_{suffix}@test.com",
        "password": "testpassword123",
    }


async def _register(client: AsyncClient, payload: dict) -> str:
    resp = await client.post("/users", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["user"]["token"]


async def _promote_to_admin(username: str) -> None:
    settings = get_app_settings()
    conn = await asyncpg.connect(str(settings.database_url))
    try:
        await conn.execute("UPDATE users SET role = 'admin' WHERE username = $1", username)
    finally:
        await conn.close()


async def _create_article(client: AsyncClient, token: str) -> str:
    title = f"rbac test {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/articles",
        json={"article": {"title": title, "description": "d", "body": "b", "tagList": []}},
        headers={"Authorization": f"Token {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["article"]["slug"]


@pytest.mark.asyncio
async def test_admin_can_delete_others_article(client: AsyncClient):
    """① 管理员能删别人的文章"""
    admin, author = _payload("admin"), _payload("author")
    admin_token = await _register(client, admin)
    await _promote_to_admin(admin["username"])
    author_token = await _register(client, author)
    slug = await _create_article(client, author_token)

    resp = await client.delete(f"/articles/{slug}", headers={"Authorization": f"Token {admin_token}"})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_author_cannot_delete_others_article(client: AsyncClient):
    """② 普通作者删别人的文章仍然 403"""
    owner, intruder = _payload("owner"), _payload("intruder")
    owner_token = await _register(client, owner)
    intruder_token = await _register(client, intruder)
    slug = await _create_article(client, owner_token)

    resp = await client.delete(f"/articles/{slug}", headers={"Authorization": f"Token {intruder_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_anonymous_gets_401_not_403(client: AsyncClient):
    """③ 匿名必须是 401，不是 403"""
    owner = _payload("owner")
    owner_token = await _register(client, owner)
    slug = await _create_article(client, owner_token)

    resp = await client.delete(f"/articles/{slug}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_delete_others_comment(client: AsyncClient):
    """④ 管理员能删别人的评论"""
    admin, author = _payload("admin"), _payload("author")
    admin_token = await _register(client, admin)
    await _promote_to_admin(admin["username"])
    author_token = await _register(client, author)
    slug = await _create_article(client, author_token)

    created = await client.post(
        f"/articles/{slug}/comments",
        json={"comment": {"body": "spam"}},
        headers={"Authorization": f"Token {author_token}"},
    )
    assert created.status_code == 201, created.text
    comment_id = created.json()["comment"]["id"]

    resp = await client.delete(
        f"/articles/{slug}/comments/{comment_id}",
        headers={"Authorization": f"Token {admin_token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_denied_request_increments_metric(client: AsyncClient):
    """⑤ 被拒一次，authz_denied_total 就 +1"""
    owner, intruder = _payload("owner"), _payload("intruder")
    owner_token = await _register(client, owner)
    intruder_token = await _register(client, intruder)
    slug = await _create_article(client, owner_token)

    denied = await client.delete(f"/articles/{slug}", headers={"Authorization": f"Token {intruder_token}"})
    assert denied.status_code == 403

    metrics = await client.get("http://testserver/metrics")
    assert 'authz_denied_total{permission="article:update:any",role="author"}' in metrics.text