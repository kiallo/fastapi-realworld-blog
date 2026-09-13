"""
Redis 会话管理演示脚本

演示内容：
1. 用户登录 → Token 存入 Redis
2. 验证会话
3. 登出 → Token 从 Redis 删除
4. 验证 Token 已失效
"""
import asyncio
import redis.asyncio as redis


async def main():
    # 连接 Redis
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    print("=" * 60)
    print("📌 Redis 会话管理演示")
    print("=" * 60)

    # --- 1. 模拟登录，存储 Token ---
    print("\n[1] 模拟用户登录，存储 Token 到 Redis...")

    username = "demo_user"
    token = "eyJhbGciOiJIUzI1NiJ9.demo_token_xxx"
    session_key = f"session:user:{username}"

    import json
    from datetime import datetime, timezone

    session_data = {
        "token": token,
        "login_time": datetime.now(timezone.utc).isoformat(),
        "device_info": "Chrome/120.0",
    }

    await r.setex(session_key, 3600, json.dumps(session_data))
    await r.sadd("online:users", username)

    print(f"   ✅ Token 已存储: {session_key}")
    print(f"   数据: {session_data}")
    print("\n   👉 现在去另一个终端执行: KEYS session:* 和 SMEMBERS online:users")
    input("   按 Enter 继续...")

    # --- 2. 验证会话 ---
    print("\n[2] 验证会话是否存在...")

    stored = await r.get(session_key)
    if stored:
        data = json.loads(stored)
        ttl = await r.ttl(session_key)
        print(f"   ✅ 会话有效")
        print(f"   用户: {username}")
        print(f"   Token: {data['token'][:30]}...")
        print(f"   登录时间: {data['login_time']}")
        print(f"   剩余有效期: {ttl} 秒")

    # --- 3. 查看在线用户 ---
    print("\n[3] 查看在线用户...")

    online_users = await r.smembers("online:users")
    print(f"   在线用户: {online_users}")

    # --- 4. 验证 Token 是否匹配 ---
    print("\n[4] 验证 Token 是否有效...")

    test_token_correct = token
    test_token_wrong = "fake_token"

    raw = await r.get(session_key)
    if raw is None:
        print("   错误: session 数据不存在")
        return
    stored_data = json.loads(raw)
    print(f"   正确 Token 验证: {stored_data['token'] == test_token_correct}")
    print(f"   错误 Token 验证: {stored_data['token'] == test_token_wrong}")

    # --- 5. 登出（删除 Token） ---
    print("\n   👉 数据即将被删除，再去 Redis 确认一下")
    input("   按 Enter 继续登出...")

    print("\n[5] 用户登出，删除 Token...")

    deleted = await r.delete(session_key)
    await r.srem("online:users", username)
    print(f"   删除结果: {'成功' if deleted else '失败'}")

    # --- 6. 验证 Token 已失效 ---
    print("\n[6] 验证 Token 已失效...")

    stored = await r.get(session_key)
    print(f"   会话存在: {stored is not None}")
    if stored is None:
        print("   ✅ Token 已失效，用户已登出")

    online_users = await r.smembers("online:users")
    print(f"   在线用户: {online_users}")

    # --- 7. Token 黑名单演示 ---
    print("\n" + "=" * 60)
    print("📌 Token 黑名单演示")
    print("=" * 60)

    blacklist_key = "token:blacklist:demo_token_123"
    await r.setex(blacklist_key, 7200, json.dumps({
        "revoked_at": datetime.now(timezone.utc).isoformat(),
        "reason": "用户主动登出"
    }))
    print(f"\n   Token 已加入黑名单: {blacklist_key}")

    exists = await r.exists(blacklist_key)
    print(f"   黑名单检查: {'在黑名单中' if exists else '不在黑名单'}")

    await r.delete(blacklist_key)
    exists = await r.exists(blacklist_key)
    print(f"   清除后检查: {'在黑名单中' if exists else '不在黑名单'}")

    # --- 清理 ---
    print("\n" + "=" * 60)
    print("✅ 演示完成！")
    print("=" * 60)

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())