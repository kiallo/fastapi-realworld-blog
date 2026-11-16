"""用户资料 Repository 测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.db.repositories.profiles import ProfilesRepository
from app.db.errors import EntityDoesNotExist
from app.models.domain.profiles import Profile


@pytest.fixture
def mock_conn():
    return MagicMock()


@pytest.fixture
def mock_user_row():
    return {
        "id": 1,
        "username": "testuser",
        "email": "test@test.com",
        "bio": "Hello world",
        "image": None,
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1),
    }


@pytest.mark.asyncio
async def test_get_profile_by_username(mock_conn, mock_user_row):
    """get_profile_by_username — 获取用户资料"""
    with patch("app.db.repositories.profiles.queries") as mock_queries:
        mock_queries.get_user_by_username = AsyncMock(return_value=mock_user_row)
        mock_queries.is_user_following_for_another = AsyncMock(
            return_value={"is_following": False}
        )

        from app.models.domain.users import User
        requested_user = User(username="otheruser", email="other@test.com", bio="", image=None)

        repo = ProfilesRepository(mock_conn)
        profile = await repo.get_profile_by_username(
            username="testuser",
            requested_user=requested_user,
        )

    assert profile.username == "testuser"
    assert profile.bio == "Hello world"
    assert profile.following is False


@pytest.mark.asyncio
async def test_get_profile_not_found(mock_conn):
    """get_profile_by_username — 用户不存在"""
    with patch("app.db.repositories.profiles.queries") as mock_queries:
        mock_queries.get_user_by_username = AsyncMock(return_value=None)

        repo = ProfilesRepository(mock_conn)
        with pytest.raises(EntityDoesNotExist):
            await repo.get_profile_by_username(username="nonexistent")


@pytest.mark.asyncio
async def test_get_profile_following_status(mock_conn, mock_user_row):
    """get_profile_by_username — 返回正确的关注状态"""
    with patch("app.db.repositories.profiles.queries") as mock_queries:
        mock_queries.get_user_by_username = AsyncMock(return_value=mock_user_row)
        mock_queries.is_user_following_for_another = AsyncMock(
            return_value={"is_following": True}
        )

        from app.models.domain.users import User
        requested_user = User(username="follower", email="f@test.com", bio="", image=None)

        repo = ProfilesRepository(mock_conn)
        profile = await repo.get_profile_by_username(
            username="testuser",
            requested_user=requested_user,
        )

    assert profile.following is True


@pytest.mark.asyncio
async def test_add_user_into_followers(mock_conn):
    """add_user_into_followers — 关注用户"""
    with patch("app.db.repositories.profiles.queries") as mock_queries:
        mock_queries.subscribe_user_to_another = AsyncMock()

        from app.models.domain.users import User
        target = User(username="target", email="t@test.com", bio="", image=None)
        requester = User(username="requester", email="r@test.com", bio="", image=None)

        repo = ProfilesRepository(mock_conn)
        await repo.add_user_into_followers(
            target_user=target,
            requested_user=requester,
        )

    mock_queries.subscribe_user_to_another.assert_called_once_with(
        mock_conn,
        follower_username="requester",
        following_username="target",
    )


@pytest.mark.asyncio
async def test_remove_user_from_followers(mock_conn):
    """remove_user_from_followers — 取消关注"""
    with patch("app.db.repositories.profiles.queries") as mock_queries:
        mock_queries.unsubscribe_user_from_another = AsyncMock()

        from app.models.domain.users import User
        target = User(username="target", email="t@test.com", bio="", image=None)
        requester = User(username="requester", email="r@test.com", bio="", image=None)

        repo = ProfilesRepository(mock_conn)
        await repo.remove_user_from_followers(
            target_user=target,
            requested_user=requester,
        )

    mock_queries.unsubscribe_user_from_another.assert_called_once_with(
        mock_conn,
        follower_username="requester",
        following_username="target",
    )
