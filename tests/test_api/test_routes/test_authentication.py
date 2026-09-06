import pytest
from httpx import AsyncClient

TEST_USER = {
    "username": "testuser",
    "email": "testuser@test.com",
    "password": "testpassword123",
}


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """测试注册成功"""
    response = await client.post("/users", json=TEST_USER)
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["username"] == TEST_USER["username"]
    assert data["user"]["email"] == TEST_USER["email"]
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