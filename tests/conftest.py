import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.core.config import get_app_settings
from app.core.settings.app import TestAppSettings
from app.main import get_application

_settings = get_app_settings()
if not isinstance(_settings, TestAppSettings):
    raise RuntimeError("测试必须用 APP_ENV=test 运行；否则会写进开发库 realworld。")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db():
    """跑测试前把测试库升到最新 schema。

    放在 session 级：一个进程只迁移一次（约 1 秒），不用每条用例都建表。
    幂等：alembic 靠 alembic_version 表判断已执行到哪一步。
    """
    settings = get_app_settings()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "app" / "db" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", str(settings.database_url))
    command.upgrade(cfg, "head")


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
