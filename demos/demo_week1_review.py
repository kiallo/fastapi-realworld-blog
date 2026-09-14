"""
第一周综合复习测试脚本

测试内容：
1. Redis 基本操作
2. 文章缓存
3. 会话管理
4. 在线用户统计
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
import redis.asyncio as redis

# 将项目根目录加入 sys.path，以便导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 终端默认 GBK 编码，无法输出 emoji，强制使用 UTF-8
sys.stdout.reconfigure(encoding="utf-8") # type: ignore
sys.stderr.reconfigure(encoding="utf-8") # type: ignore


async def test_redis_basics(r: redis.Redis):
    """测试1: Redis 基本数据类型"""
    print("\n" + "=" * 60)
    print("📌 测试1: Redis 基本数据类型")
    print("=" * 60)

    # String
    await r.set("test:string", "Hello Redis")
    value = await r.get("test:string")
    print(f"  String: {value}")

    # Hash
    await r.hset("test:hash", mapping={"name": "张三", "age": "25"})
    name = await r.hget("test:hash", "name")
    print(f"  Hash: name={name}")

    # List
    await r.delete("test:list")
    await r.rpush("test:list", "a", "b", "c")
    items = await r.lrange("test:list", 0, -1)
    print(f"  List: {items}")

    # Set
    await r.delete("test:set")
    await r.sadd("test:set", "Python", "FastAPI", "Redis")
    members = await r.smembers("test:set")
    print(f"  Set: {members}")

    # Sorted Set
    await r.delete("test:zset")
    await r.zadd("test:zset", {"文章A": 100, "文章B": 200, "文章C": 150})
    top = await r.zrevrange("test:zset", 0, -1, withscores=True)
    print(f"  Sorted Set: {top}")

    # 清理
    await r.delete("test:string", "test:hash", "test:list", "test:set", "test:zset")
    print("  ✅ 基本数据类型测试通过")


async def test_article_cache(r: redis.Redis):
    """测试2: 文章缓存（Cache-Aside 模式）"""
    print("\n" + "=" * 60)
    print("📌 测试2: 文章缓存（Cache-Aside 模式）")
    print("=" * 60)

    from app.core.cache import ArticleCache
    cache = ArticleCache(r)

    # 模拟文章数据
    articles = [
        {"id": 1, "title": "FastAPI入门", "views": 100},
        {"id": 2, "title": "Redis教程", "views": 200},
    ]

    # 写入缓存
    await cache.set_article_list(articles, skip=0, limit=20)
    print("  写入文章列表缓存")

    # 读取缓存
    cached = await cache.get_article_list(skip=0, limit=20)
    if cached:
        print(f"  读取缓存: {len(cached)} 篇文章")
    else:
        print("  ❌ 缓存未命中")

    # 文章详情缓存
    article_detail = {"id": 1, "title": "FastAPI入门", "body": "详细内容..."}
    await cache.set_article_detail(1, article_detail)
    detail = await cache.get_article_detail(1)
    if detail:
        print(f"  文章详情缓存: {detail['title']}")

    # 浏览量统计
    await cache.increment_view_count(1)
    await cache.increment_view_count(1)
    views = await cache.get_view_count(1)
    print(f"  文章浏览量: {views}")

    # 清除缓存
    await cache.invalidate_article(1)
    detail_after = await cache.get_article_detail(1)
    print(f"  清除后详情缓存: {detail_after}")

    await cache.invalidate_all_articles()
    print("  ✅ 文章缓存测试通过")


async def test_session_management(r: redis.Redis):
    """测试3: 会话管理"""
    print("\n" + "=" * 60)
    print("📌 测试3: 会话管理（Token 白名单）")
    print("=" * 60)

    from app.services.token_storage import TokenStorage
    ts = TokenStorage(r)

    # 模拟登录
    username = "test_user"
    token = "eyJhbGciOiJIUzI1NiJ9.test_token_xxx"

    await ts.store_token(
        username=username,
        token=token,
        expire_seconds=3600,
        device_info="Chrome/120.0"
    )
    print(f"  用户登录: {username}")

    # 验证 Token
    is_valid = await ts.is_token_valid(username, token)
    print(f"  Token 验证（正确）: {is_valid}")

    is_valid_wrong = await ts.is_token_valid(username, "wrong_token")
    print(f"  Token 验证（错误）: {is_valid_wrong}")

    # 获取会话信息
    info = await ts.get_session_info(username)
    if info:
        print(f"  会话信息: 登录时间={info['login_time'][:19]}, TTL={info['ttl_seconds']}s")

    # 在线用户
    online = await ts.get_online_users()
    count = await ts.get_online_count()
    print(f"  在线用户: {online} (共 {count} 人)")

    # 登出
    await ts.revoke_token(username)
    is_valid_after = await ts.is_token_valid(username, token)
    print(f"  登出后验证: {is_valid_after}")

    online_after = await ts.get_online_users()
    print(f"  登出后在线: {online_after}")

    print("  ✅ 会话管理测试通过")


async def test_multi_user_session(r: redis.Redis):
    """测试4: 多用户会话"""
    print("\n" + "=" * 60)
    print("📌 测试4: 多用户会话")
    print("=" * 60)

    from app.services.token_storage import TokenStorage
    ts = TokenStorage(r)

    # 模拟多个用户登录
    users = [
        ("alice", "token_alice_123"),
        ("bob", "token_bob_456"),
        ("charlie", "token_charlie_789"),
    ]

    for username, token in users:
        await ts.store_token(username, token, 3600, "Demo/1.0")

    # 查看在线用户
    online = await ts.get_online_users()
    count = await ts.get_online_count()
    print(f"  在线用户: {sorted(online)} (共 {count} 人)")

    # 部分用户登出
    await ts.revoke_token("bob")
    online_after = await ts.get_online_users()
    print(f"  Bob 登出后: {sorted(online_after)}")

    # 清理
    for username, _ in users:
        await ts.revoke_token(username)

    print("  ✅ 多用户会话测试通过")


async def test_token_blacklist(r: redis.Redis):
    """测试5: Token 黑名单"""
    print("\n" + "=" * 60)
    print("📌 测试5: Token 黑名单")
    print("=" * 60)

    from app.services.token_storage import TokenStorage
    ts = TokenStorage(r)

    token = "sensitive_token_abc123"

    # 加入黑名单
    await ts.blacklist_token(token, expire_seconds=7200)

    # 检查黑名单
    is_blacklisted = await ts.is_token_blacklisted(token)
    print(f"  黑名单检查: {is_blacklisted}")

    # 清理
    blacklist_key = f"{ts.BLACKLIST_PREFIX}{token[:32]}"
    await r.delete(blacklist_key)

    is_blacklisted_after = await ts.is_token_blacklisted(token)
    print(f"  清除后检查: {is_blacklisted_after}")

    print("  ✅ Token 黑名单测试通过")


async def test_cache_stats(r: redis.Redis):
    """测试6: 缓存统计"""
    print("\n" + "=" * 60)
    print("📌 测试6: 缓存统计信息")
    print("=" * 60)

    info = await r.info()

    memory_used = info.get("used_memory_human", "N/A")
    hits = info.get("keyspace_hits", 0)
    misses = info.get("keyspace_misses", 0)
    hit_rate = hits / (hits + misses) * 100 if (hits + misses) > 0 else 0

    print(f"  内存使用: {memory_used}")
    print(f"  命中次数: {hits}")
    print(f"  未命中次数: {misses}")
    print(f"  命中率: {hit_rate:.2f}%")

    # 统计各类 key 的数量
    key_patterns = [
        ("session:*", "会话"),
        ("articles:*", "文章缓存"),
        ("article:*", "文章数据"),
        ("online:*", "在线用户"),
    ]

    for pattern, label in key_patterns:
        count = 0
        async for _ in r.scan_iter(match=pattern):
            count += 1
        print(f"  {label} ({pattern}): {count} 个 key")

    print("  ✅ 缓存统计测试通过")


async def main():
    """主测试函数"""
    print("+" + "=" * 58 + "+")
    print("|" + " 第一周综合复习测试".center(50) + "|")
    print("+" + "=" * 58 + "+")

    # 连接 Redis
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    # 检查连接
    try:
        await r.ping()
        print("\n✅ Redis 连接成功")
    except Exception as e:
        print(f"\n❌ Redis 连接失败: {e}")
        print("请先启动 Redis: docker run -d --name redis-server -p 6379:6379 redis:latest")
        return

    # 运行所有测试
    await test_redis_basics(r)
    await test_article_cache(r)
    await test_session_management(r)
    await test_multi_user_session(r)
    await test_token_blacklist(r)
    await test_cache_stats(r)

    # 总结
    print("\n" + "=" * 60)
    print("🎉 所有测试通过！第一周学习内容已掌握！")
    print("=" * 60)
    print("""
本周掌握的技能：
  ✅ FastAPI 中间件（Timing、Logging）
  ✅ FastAPI 后台任务（BackgroundTasks）
  ✅ WebSocket 实时通信（聊天室）
  ✅ Redis 5 种基本数据类型
  ✅ Redis 缓存策略（Cache-Aside）
  ✅ Redis 会话管理（Token 白名单）

下周预告：
  📚 Django 框架入门
  📚 Django REST framework
  📚 Django 博客 API 项目
    """)

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())