import asyncpg
from fastapi import FastAPI
from loguru import logger


async def connect_to_db(app: FastAPI) -> None:
    """
    启动事件：创建数据库连接池

    连接池 vs 单连接：
    - 连接池预创建多个连接，请求到来时直接取用，用完归还
    - 单连接每次请求都要建立/断开，开销巨大
    """
    logger.info("正在连接数据库...")

    try:
        pool = await asyncpg.create_pool(
            dsn=str(app.state.settings.database_url),  # 来自配置
            min_size=2,   # 最小连接数（空闲时保持的连接）
            max_size=10,  # 最大连接数（并发高峰时）
        )
        app.state.pool = pool
        logger.info("数据库连接池已就绪")
    except Exception as e:
        logger.warning(f"数据库连接失败，跳过: {e}")
        app.state.pool = None


async def close_db_connection(app: FastAPI) -> None:
    """关闭事件：释放连接池"""
    logger.info("正在关闭数据库连接...")

    if hasattr(app.state, "pool"):
        await app.state.pool.close()

    logger.info("数据库连接已关闭")