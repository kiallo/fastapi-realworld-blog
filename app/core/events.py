from typing import Callable
from fastapi import FastAPI
from loguru import logger

def create_start_app_handler(app: FastAPI) -> Callable:
    """创建启动事件处理器"""

    async def start_app() -> None:
        logger.info("🚀 应用启动中...")
        # 这里将来会初始化数据库连接池
        # app.state.pool = await asyncpg.create_pool(...)
        logger.info("✅ 应用启动完成")

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    """创建关闭事件处理器"""

    async def stop_app() -> None:
        logger.info("🛑 应用关闭中...")
        # 这里将来会关闭数据库连接池
        # if hasattr(app.state, "pool"):
        #     await app.state.pool.close()
        logger.info("✅ 应用已安全关闭")

    return stop_app