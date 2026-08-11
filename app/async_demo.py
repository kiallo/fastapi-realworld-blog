"""
第 1 课练习：理解 async/await
运行方式：python app/async_demo.py
"""
import asyncio
from typing import Optional


# ========== 1. 普通函数 vs 协程函数 ==========

def normal_function() -> str:
    """普通函数：调用就立即执行，返回结果"""
    return "我是普通函数"

async def coroutine_function() -> str:
    """协程函数：调用返回协程对象，需要用 await 或 asyncio.run() 驱动"""
    await asyncio.sleep(0.1)  # 模拟异步等待
    return "我是协程函数"


# ========== 2. 并发执行 — 异步的优势 ==========

async def fetch_user(user_id: int) -> dict:
    """模拟从数据库查询用户"""
    await asyncio.sleep(0.5)  # 模拟 I/O 等待
    return {"id": user_id, "name": f"用户{user_id}"}


async def demo_concurrent():
    """
    并发查询 3 个用户 — 总耗时 ~0.5 秒，而不是 1.5 秒
    这就是 FastAPI 高性能的秘密
    """
    print("开始并发查询 3 个用户...")

    # 同时发起 3 个查询，等待全部完成
    results = await asyncio.gather(
        fetch_user(1),
        fetch_user(2),
        fetch_user(3),
    )
    print(f"结果：{results}")


# ========== 3. 类型注解 — FastAPI 的核心依赖 ==========

# Optional[X] 等价于 Union[X, None]（Python 3.10+ 可以写 X | None）
def greet(name: str, title: Optional[str] = None) -> str:
    """title 是可选的，可以是 str 或 None"""
    if title:
        return f"你好，{title} {name}"
    return f"你好，{name}"


# Python 3.9+ 可以用小写 list/dict 代替 List/Dict
def process_items(items: list[str]) -> dict[str, int]:
    """输入字符串列表，返回字符串→长度的字典"""
    return {item: len(item) for item in items}


# ========== 4. 异步上下文管理器 — 管理资源生命周期 ==========

class AsyncConnection:
    """模拟数据库连接"""

    async def connect(self):
        print("  → 连接数据库...")
        await asyncio.sleep(0.1)

    async def close(self):
        print("  → 关闭连接...")
        await asyncio.sleep(0.05)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()


async def demo_async_context():
    """async with 自动管理资源"""
    async with AsyncConnection() as conn:
        print("  → 执行查询...")
    print("  → 连接已自动关闭")


# ========== 运行入口 ==========

async def main():
    print("=" * 50)
    print("第 1 课：Python 异步与类型注解")
    print("=" * 50)

    # 1. 普通函数 vs 协程
    print("\n1. 普通函数 vs 协程函数：")
    print(f"   普通函数：{normal_function()}")
    result = await coroutine_function()
    print(f"   协程函数：{result}")

    # 2. 并发
    print("\n2. 并发查询演示：")
    import time
    start = time.time()
    await demo_concurrent()
    print(f"   耗时：{time.time() - start:.2f} 秒")

    # 3. 类型注解
    print("\n3. 类型注解：")
    print(f"   {greet('小明')}")
    print(f"   {greet('小明', '博士')}")
    print(f"   {process_items(['apple', 'banana', 'cherry'])}")

    # 4. 异步上下文管理器
    print("\n4. 异步上下文管理器：")
    await demo_async_context()

    print("\n✅ 全部演示完成！")


if __name__ == "__main__":
    asyncio.run(main())
