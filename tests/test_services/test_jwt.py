"""JWT 服务测试"""
import pytest
from datetime import timedelta

from app.services.jwt import (
    create_access_token_for_user,
    create_jwt_token,
    get_username_from_token,
)


SECRET_KEY = "test-secret-key-for-jwt"


@pytest.fixture
def sample_token():
    """创建一个测试用 Token"""
    return create_access_token_for_user(
        user_username="testuser",
        secret_key=SECRET_KEY,
        expires_delta=timedelta(hours=1),
    )


def test_create_jwt_token_returns_string(sample_token):
    """create_jwt_token — 返回字符串格式的 JWT"""
    assert isinstance(sample_token, str)
    assert len(sample_token.split(".")) == 3  # Header.Payload.Signature


def test_get_username_from_valid_token(sample_token):
    """get_username_from_token — 从有效 Token 中提取用户名"""
    username = get_username_from_token(token=sample_token, secret_key=SECRET_KEY)
    assert username == "testuser"


def test_get_username_from_expired_token():
    """get_username_from_token — 过期 Token 返回 None"""
    token = create_access_token_for_user(
        user_username="testuser",
        secret_key=SECRET_KEY,
        expires_delta=timedelta(seconds=-1),  # 已过期
    )
    username = get_username_from_token(token=token, secret_key=SECRET_KEY)
    assert username is None


def test_get_username_from_invalid_token():
    """get_username_from_token — 无效 Token 返回 None"""
    username = get_username_from_token(token="invalid.token.here", secret_key=SECRET_KEY)
    assert username is None


def test_get_username_from_wrong_secret():
    """get_username_from_token — 密钥不匹配返回 None"""
    token = create_access_token_for_user(
        user_username="testuser",
        secret_key=SECRET_KEY,
        expires_delta=timedelta(hours=1),
    )
    username = get_username_from_token(token=token, secret_key="wrong-secret")
    assert username is None


def test_create_jwt_token_with_custom_content():
    """create_jwt_token — 自定义内容"""
    token = create_jwt_token(
        jwt_content={"username": "alice", "role": "admin"},
        secret_key=SECRET_KEY,
        expires_delta=timedelta(hours=2),
    )
    username = get_username_from_token(token=token, secret_key=SECRET_KEY)
    assert username == "alice"


def test_different_users_get_different_tokens():
    """不同用户生成不同的 Token"""
    token1 = create_access_token_for_user(
        user_username="user1",
        secret_key=SECRET_KEY,
        expires_delta=timedelta(hours=1),
    )
    token2 = create_access_token_for_user(
        user_username="user2",
        secret_key=SECRET_KEY,
        expires_delta=timedelta(hours=1),
    )
    assert token1 != token2
