from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.api import router as api_router
from app.core.config import get_app_settings
from app.core.middleware import TimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理（替代已弃用的 on_event）

    yield 之前 = 启动逻辑（startup）
    yield 之后 = 关闭逻辑（shutdown）
    """
    # --- 启动 ---
    settings = app.state.settings
    logger.info("正在连接数据库...")
    try:
        pool = await asyncpg.create_pool(
            dsn=str(settings.database_url),
            min_size=2,
            max_size=10,
        )
        app.state.pool = pool
        logger.info("数据库连接池已就绪")
    except Exception as e:
        logger.warning(f"数据库连接失败，跳过: {e}")
        app.state.pool = None

    yield  # 应用在此处运行，处理请求

    # --- 关闭 ---
    logger.info("正在关闭数据库连接...")
    if hasattr(app.state, "pool") and app.state.pool is not None:
        await app.state.pool.close()
    logger.info("数据库连接已关闭")


def get_application() -> FastAPI:
    """
    应用工厂函数

    为什么用工厂函数？
    1. 测试隔离：每个测试用例获得全新的 App 实例
    2. 多环境：dev/prod/test 自然切换
    3. 延迟初始化：不是导入时立即创建，而是显式调用时才创建
    """
    # ① 获取配置
    settings = get_app_settings()

    # ② 配置日志
    settings.configure_logging()

    # ③ 创建 FastAPI 实例（绑定生命周期）
    application = FastAPI(lifespan=lifespan, **settings.fastapi_kwargs)

    # 把配置挂到 app.state 上（方便各模块访问）
    application.state.settings = settings

    # ④ 添加中间件（CORS — 允许跨域请求）
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],           # 开发阶段允许所有来源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(TimingMiddleware)

    # ⑤ 挂载路由
    application.include_router(api_router)

    return application


# uvicorn 入口：uvicorn app.main:app
app = get_application()