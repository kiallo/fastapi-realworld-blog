import asyncio
import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from app.main import get_application


@pytest.fixture(scope="session")
def event_loop():
    """创建全局事件循环（scope="session" 必须用这个模式）"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def app():
    """
    创建测试用 FastAPI 应用

    每次测试都创建全新的 app 实例 — 这就是工厂模式的价值
    """
    app = get_application()
    return app


@pytest.fixture
async def initialized_app(app):
    """
    模拟启动事件的应用（管理生命周期）

    LifespanManager 自动触发 startup/shutdown 事件
    模拟真实运行环境
    """
    async with LifespanManager(app) as manager:
        yield manager.app


@pytest.fixture
async def client(initialized_app):
    """
    测试 HTTP 客户端

    httpx 的 ASGITransport 直接与 FastAPI 内存通信
    不需要真实启动 HTTP 服务器 — 速度快几百倍
    """
    async with AsyncClient(
        transport=ASGITransport(app=initialized_app),
        base_url="http://testserver/api",
    ) as client:
        yield client