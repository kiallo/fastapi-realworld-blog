import uuid

import pytest
from httpx import AsyncClient


def _unique_user_payload():
    """生成唯一用户名。

    这个测试连的是真实 PostgreSQL（APP_ENV 默认 dev），
    写死 testuser 的话第二次跑就会因为「用户已存在」返回 400。
    """
    suffix = uuid.uuid4().hex[:8]
    return {
        "username": f"testuser_{suffix}",
        "email": f"testuser_{suffix}@test.com",
        "password": "testpassword123",
    }


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """测试注册成功"""
    payload = _unique_user_payload()
    response = await client.post("/users", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["user"]["username"] == payload["username"]
    assert data["user"]["email"] == payload["email"]
    assert "token" in data["user"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """测试重复注册"""
    # 第一次注册
    await client.post("/users", json={
        "username": "unique123",
        "email": "unique123@test.com",
        "password": "test123456",
    })
    # 第二次注册同用户名
    response = await client.post("/users", json={
        "username": "unique123",
        "email": "unique123_other@test.com",
        "password": "test123456",
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """测试登录成功"""
    # 先注册
    await client.post("/users", json={
        "username": "loginuser",
        "email": "loginuser@test.com",
        "password": "test123456",
    })
    # 再登录
    response = await client.post("/users/login", json={
        "email": "loginuser@test.com",
        "password": "test123456",
    })
    assert response.status_code == 200
    assert "token" in response.json()["user"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """测试错误密码登录"""
    response = await client.post("/users/login", json={
        "email": "loginuser@test.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 400