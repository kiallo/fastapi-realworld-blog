import json
from datetime import datetime, timezone
from typing import Optional
import redis.asyncio as redis
from loguru import logger


class TokenStorage:
    """
    Redis Token 存储管理器

    采用白名单策略：Token 必须在 Redis 中才有效
    """

    # Key 前缀
    SESSION_PREFIX = "session:user:"      # 用户会话
    BLACKLIST_PREFIX = "token:blacklist:"  # Token 黑名单
    ONLINE_USERS_KEY = "online:users"      # 在线用户集合

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def store_token(
        self,
        username: str,
        token: str,
        expire_seconds: int,
        device_info: str = "unknown"
    ) -> bool:
        """
        存储用户 Token（白名单）

        参数：
            username: 用户名
            token: JWT Token 字符串
            expire_seconds: Token 过期时间（秒）
            device_info: 设备信息
        """
        session_key = f"{self.SESSION_PREFIX}{username}"
        session_data = {
            "token": token,
            "login_time": datetime.now(timezone.utc).isoformat(),
            "device_info": device_info,
        }

        try:
            # 存储会话数据，设置过期时间
            await self.redis.setex(
                session_key,
                expire_seconds,
                json.dumps(session_data)
            )

            # 添加到在线用户集合
            await self.redis.sadd(self.ONLINE_USERS_KEY, username)

            logger.info(f"✅ Token 已存储: {username} (TTL: {expire_seconds}s)")
            return True
        except Exception as e:
            logger.error(f"❌ Token 存储失败: {e}")
            return False


    async def get_token(self, username: str) -> Optional[str]:
        """
        获取用户的当前 Token

        返回 None 表示用户未登录或 Token 已过期
        """
        session_key = f"{self.SESSION_PREFIX}{username}"

        try:
            data = await self.redis.get(session_key)
            if data:
                session = json.loads(data)
                return session.get("token")
            return None
        except Exception as e:
            logger.error(f"获取 Token 失败: {e}")
            return None


    async def get_session_info(self, username: str) -> Optional[dict]:
        """获取用户会话详情"""
        session_key = f"{self.SESSION_PREFIX}{username}"

        try:
            data = await self.redis.get(session_key)
            if data:
                session = json.loads(data)
                # 计算剩余时间
                ttl = await self.redis.ttl(session_key)
                session["ttl_seconds"] = ttl
                return session
            return None
        except Exception as e:
            logger.error(f"获取会话信息失败: {e}")
            return None


    async def is_token_valid(self, username: str, token: str) -> bool:
        """
        验证 Token 是否有效

        白名单策略：Token 必须和 Redis 中存储的一致
        """
        stored_token = await self.get_token(username)
        if stored_token is None:
            return False
        return stored_token == token


    async def revoke_token(self, username: str) -> bool:
        """
        撤销用户 Token（登出）

        从 Redis 中删除会话记录
        """
        session_key = f"{self.SESSION_PREFIX}{username}"

        try:
            # 获取当前会话信息（用于记录日志）
            data = await self.redis.get(session_key)

            # 删除会话
            deleted = await self.redis.delete(session_key)

            # 从在线用户集合中移除
            await self.redis.srem(self.ONLINE_USERS_KEY, username)

            if deleted:
                logger.info(f"🚪 Token 已撤销: {username}")
                return True
            else:
                logger.warning(f"⚠️ Token 不存在: {username}")
                return False
        except Exception as e:
            logger.error(f"❌ Token 撤销失败: {e}")
            return False


    async def blacklist_token(
        self,
        token: str,
        expire_seconds: int
    ) -> bool:
        """
        将 Token 加入黑名单

        用于需要主动失效但不想删除会话的场景
        黑名单条目的 TTL 等于 Token 剩余有效期
        """
        blacklist_key = f"{self.BLACKLIST_PREFIX}{token[:32]}"  # 用 Token 前32字符作为 key

        try:
            await self.redis.setex(
                blacklist_key,
                expire_seconds,
                json.dumps({"revoked_at": datetime.now(timezone.utc).isoformat()})
            )
            logger.info(f"🚫 Token 已加入黑名单 (TTL: {expire_seconds}s)")
            return True
        except Exception as e:
            logger.error(f"❌ 加入黑名单失败: {e}")
            return False


    async def is_token_blacklisted(self, token: str) -> bool:
        """检查 Token 是否在黑名单中"""
        blacklist_key = f"{self.BLACKLIST_PREFIX}{token[:32]}"

        try:
            exists = await self.redis.exists(blacklist_key)
            return bool(exists)
        except Exception as e:
            logger.error(f"检查黑名单失败: {e}")
            return False


    async def get_online_users(self) -> list:
        """获取在线用户列表"""
        try:
            users = await self.redis.smembers(self.ONLINE_USERS_KEY)
            return list(users)
        except Exception as e:
            logger.error(f"获取在线用户失败: {e}")
            return []


    async def get_online_count(self) -> int:
        """获取在线用户数量"""
        try:
            return await self.redis.scard(self.ONLINE_USERS_KEY)
        except Exception as e:
            logger.error(f"获取在线用户数量失败: {e}")
            return 0


    async def force_logout(self, username: str) -> bool:
        """
        强制用户下线

        等同于 revoke_token，但语义更明确
        """
        return await self.revoke_token(username)

    async def revoke_all_tokens(self) -> int:
        """
        撤销所有用户 Token（紧急情况使用）

        返回撤销的用户数量
        """
        try:
            users = await self.get_online_users()
            count = 0
            for username in users:
                if await self.revoke_token(username):
                    count += 1
            logger.warning(f"⚠️ 已撤销所有 Token: {count} 个用户")
            return count
        except Exception as e:
            logger.error(f"撤销所有 Token 失败: {e}")
            return 0