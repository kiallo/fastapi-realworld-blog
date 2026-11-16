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
    """测试重复注册：同一用户名第二次必须 400"""
    payload = {
        "username": "unique123",
        "email": "unique123@test.com",
        "password": "test123456",
    }
    # 第一次可能是 201（全新库）也可能是 400（库里已有这个用户），都接受。
    # 但要显式断言，避免像原版那样把第一次的结果静默吞掉。
    first = await client.post("/users", json=payload)
    assert first.status_code in (201, 400)

    second = await client.post(
        "/users",
        json={**payload, "email": "unique123_other@test.com"},
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """测试登录成功：注册一个全新用户后立即登录，不依赖库里的残留数据"""
    payload = _unique_user_payload()
    register = await client.post("/users", json=payload)
    assert register.status_code == 201, "新用户注册必须成功，否则登录测试的前提不成立"

    response = await client.post(
        "/users/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert response.status_code == 200
    assert "token" in response.json()["user"]


@pytest.mark.asyncio
async def test_login_with_invalid_credentials_returns_400(client: AsyncClient):
    """密码错误与用户不存在必须返回完全相同的 400（防用户名枚举）

    原来叫 test_login_wrong_password，但它只断言「返回 400」——
    而「用户不存在」也返回 400，所以它可能在验证另一件事却毫不知情。
    现在把两种失败放在一起对比，才真正锁住了防枚举的设计。
    """
    payload = _unique_user_payload()
    await client.post("/users", json=payload)   # 确保这个用户真实存在

    wrong_password = await client.post(
        "/users/login",
        json={"email": payload["email"], "password": "definitely-wrong"},
    )
    unknown_user = await client.post(
        "/users/login",
        json={
            "email": f"nobody_{uuid.uuid4().hex[:8]}@nowhere.com",
            "password": "whatever",
        },
    )

    assert wrong_password.status_code == 400
    assert unknown_user.status_code == 400
    assert wrong_password.json() == unknown_user.json()