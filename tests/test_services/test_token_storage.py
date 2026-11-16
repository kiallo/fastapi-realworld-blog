"""Redis 会话存储（白名单）测试。

这是认证链路里最容易被忽略、但错了后果最严重的一层：
登出、强制下线、单点登录全靠它。
全部用 fakeredis 内存实例，不连真实 Redis。

decode_responses=True 必须和 app/core/dependencies.py 的建连参数一致，
否则 get() 返回 bytes，json.loads 行为和断言取值都要跟着变。
"""

import fakeredis.aioredis
import pytest

from app.services.token_storage import TokenStorage


@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()


@pytest.fixture
def storage(redis_client):
    return TokenStorage(redis_client)


class TestStoreToken:
    async def test_returns_true_and_sets_ttl(self, storage, redis_client):
        assert await storage.store_token("alice", "sid-1", 600) is True

        assert await redis_client.ttl("session:user:alice") > 0
        stored = await redis_client.get("session:user:alice")
        assert "sid-1" in stored

    async def test_adds_user_to_online_set(self, storage):
        await storage.store_token("alice", "sid-1", 600)

        assert await storage.get_online_users() == ["alice"]
        assert await storage.get_online_count() == 1

    async def test_second_login_replaces_session(self, storage):
        """单点登录：同一用户再次登录，旧 sid 必须立刻失效"""
        await storage.store_token("alice", "old-sid", 600)
        await storage.store_token("alice", "new-sid", 600)

        assert await storage.get_session_id("alice") == "new-sid"
        assert await storage.is_session_valid("alice", "old-sid") is False
        assert await storage.is_session_valid("alice", "new-sid") is True


class TestGetSessionId:
    async def test_missing_returns_none(self, storage):
        assert await storage.get_session_id("nobody") is None

    async def test_returns_stored_sid(self, storage):
        await storage.store_token("alice", "sid-1", 600)
        assert await storage.get_session_id("alice") == "sid-1"

    async def test_corrupted_json_degrades_to_none(self, storage, redis_client):
        """Redis 里存了非 JSON 时不能抛异常炸掉整条认证链路"""
        await redis_client.set("session:user:broken", "not-a-json")
        assert await storage.get_session_id("broken") is None


class TestGetSessionInfo:
    async def test_includes_ttl_and_device(self, storage):
        await storage.store_token("alice", "sid-1", 600, device_info="pytest")

        info = await storage.get_session_info("alice")

        assert info["session_id"] == "sid-1"
        assert info["device_info"] == "pytest"
        assert info["ttl_seconds"] > 0
        assert "login_time" in info

    async def test_missing_returns_none(self, storage):
        assert await storage.get_session_info("nobody") is None


class TestIsSessionValid:
    async def test_matching_sid_is_valid(self, storage):
        await storage.store_token("alice", "sid-1", 600)
        assert await storage.is_session_valid("alice", "sid-1") is True

    async def test_mismatched_sid_is_invalid(self, storage):
        """「登出后旧 token 立刻 401」靠的就是这一条"""
        await storage.store_token("alice", "sid-1", 600)
        assert await storage.is_session_valid("alice", "sid-2") is False

    async def test_empty_sid_short_circuits(self, storage):
        """空 sid 直接返回 False，不会去查 Redis"""
        await storage.store_token("alice", "sid-1", 600)
        assert await storage.is_session_valid("alice", "") is False

    async def test_no_session_is_invalid(self, storage):
        assert await storage.is_session_valid("nobody", "any-sid") is False


class TestRevokeToken:
    async def test_revoke_deletes_session_and_online_entry(self, storage, redis_client):
        await storage.store_token("alice", "sid-1", 600)

        assert await storage.revoke_token("alice") is True
        assert await redis_client.exists("session:user:alice") == 0
        assert await storage.get_online_users() == []
        assert await storage.is_session_valid("alice", "sid-1") is False

    async def test_revoke_unknown_user_returns_false(self, storage):
        """重复登出不该报错，但要如实返回 False"""
        assert await storage.revoke_token("nobody") is False

    async def test_force_logout_behaves_like_revoke(self, storage):
        await storage.store_token("bob", "sid-9", 600)

        assert await storage.force_logout("bob") is True
        assert await storage.get_session_id("bob") is None


class TestBlacklist:
    async def test_blacklist_roundtrip(self, storage):
        token = "a" * 40

        assert await storage.blacklist_token(token, 60) is True
        assert await storage.is_token_blacklisted(token) is True

    async def test_unknown_token_is_not_blacklisted(self, storage):
        assert await storage.is_token_blacklisted("never-seen") is False

    async def test_blacklist_key_uses_first_32_chars(self, storage, redis_client):
        """实现细节：key 取 token 前 32 字符，两个 token 前缀相同会互相影响"""
        token = "x" * 40
        await storage.blacklist_token(token, 60)

        assert await redis_client.exists(f"token:blacklist:{token[:32]}") == 1


class TestRevokeAll:
    async def test_revokes_every_online_user(self, storage):
        for name in ("alice", "bob", "carol"):
            await storage.store_token(name, f"sid-{name}", 600)

        assert await storage.revoke_all_tokens() == 3
        assert await storage.get_online_users() == []
