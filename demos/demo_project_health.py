"""
项目健康检查脚本

检查项目所有组件是否正常工作
"""
import asyncio
import redis.asyncio as redis


async def check_redis():
    """检查 Redis 连接"""
    print("🔍 检查 Redis 连接...")
    try:
        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        await r.ping()
        info = await r.info("server")
        version = info.get("redis_version", "unknown")
        print(f"   ✅ Redis 连接成功 (版本: {version})")
        await r.aclose()
        return True
    except Exception as e:
        print(f"   ❌ Redis 连接失败: {e}")
        return False


async def check_redis_keys():
    """检查 Redis 中的 key 分布"""
    print("\n🔍 检查 Redis 数据...")
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    patterns = {
        "session:*": "用户会话",
        "articles:*": "文章缓存",
        "article:*": "文章数据",
        "online:*": "在线用户",
        "token:*": "Token 黑名单",
    }

    total = 0
    for pattern, label in patterns.items():
        count = 0
        async for _ in r.scan_iter(match=pattern):
            count += 1
        total += count
        status = "✅" if count >= 0 else "⚠️"
        print(f"   {status} {label}: {count} 个 key")

    print(f"   📊 总计: {total} 个 key")
    await r.aclose()


def check_project_files():
    """检查项目关键文件"""
    import os

    print("\n🔍 检查项目文件...")

    required_files = [
        "app/main.py",
        "app/core/middleware.py",
        "app/core/dependencies.py",
        "app/core/cache.py",
        "app/core/redis_utils.py",
        "app/services/token_storage.py",
        "app/services/jwt.py",
        "app/api/routes/api.py",
        "app/api/routes/authentication.py",
        "app/api/routes/demo/cache.py",
        "app/api/routes/demo/cache_stats.py",
        "app/api/routes/demo/session.py",
        "app/api/routes/demo/tasks.py",
        "app/api/routes/demo/websocket.py",
    ]

    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} (缺失)")


async def main():
    print("╔" + "═" * 50 + "╗")
    print("║" + " 项目健康检查".center(44) + "║")
    print("╚" + "═" * 50 + "╝")

    # 检查文件
    check_project_files()

    # 检查 Redis
    redis_ok = await check_redis()

    if redis_ok:
        await check_redis_keys()

    # 总结
    print("\n" + "=" * 50)
    print("📋 检查完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())