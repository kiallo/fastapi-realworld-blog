import hmac
import json
from datetime import datetime, timezone
from typing import Optional
import redis.asyncio as redis
from loguru import logger


class TokenStorage:
    """
    Redis 会话存储管理器

    采用白名单策略：JWT 里的 sid 必须在 Redis 中存在且一致，票据才算有效。
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
        session_id: str,
        expire_seconds: int,
        device_info: str = "unknown"
    ) -> bool:
        """
        存储用户会话（白名单）

        参数：
            username: 用户名
            session_id: 会话 ID（sid）—— ⚠️ 存的是随机 sid，**不是 JWT 原文**
            expire_seconds: 会话过期时间（秒）
            device_info: 设备信息

        为什么存 sid 不存 token 原文：
        ① Redis 泄漏时，攻击者拿到 sid 也换不出可用 token（token 还需要签名）
        ② sid 比 JWT 短得多，省内存
        """
        session_key = f"{self.SESSION_PREFIX}{username}"
        session_data = {
            "session_id": session_id,
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

            logger.info(f"✅ 会话已存储: {username} (TTL: {expire_seconds}s)")
            return True
        except Exception as e:
            logger.error(f"❌ 会话存储失败: {e}")
            return False


    async def get_session_id(self, username: str) -> Optional[str]:
        """
        获取用户当前的会话 ID

        返回 None 表示用户未登录或会话已过期
        """
        session_key = f"{self.SESSION_PREFIX}{username}"

        try:
            data = await self.redis.get(session_key)
            if data:
                session = json.loads(data)
                return session.get("session_id")
            return None
        except Exception as e:
            logger.error(f"获取会话 ID 失败: {e}")
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


    async def is_session_valid(self, username: str, session_id: str) -> bool:
        """
        验证会话是否有效

        白名单策略：JWT 里带的 sid 必须和 Redis 中存的一致。
        登出 = 把 Redis 里的 key 删掉 → 同一个 JWT 立刻失效。
        """
        if not session_id:
            return False

        stored_session_id = await self.get_session_id(username)
        if stored_session_id is None:
            return False

        # 用常量时间比较，避免"逐字符比较提前返回"泄漏出前几位正确的内容
        return hmac.compare_digest(stored_session_id, session_id)


    async def revoke_token(self, username: str) -> bool:
        """
        撤销用户会话（登出）

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