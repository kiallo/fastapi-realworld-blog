import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_returns_ok(client: AsyncClient):
    """测试根路径健康检查"""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_ping_returns_pong(client: AsyncClient):
    """测试 Ping 端点"""
    response = await client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}


@pytest.mark.asyncio
async def test_user_id_type_validation(client: AsyncClient):
    """测试路径参数类型校验"""
    response = await client.get("/users/abc")
    assert response.status_code == 422
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_items_pagination_params(client: AsyncClient):
    """测试查询参数"""
    response = await client.get("/items?page=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 5