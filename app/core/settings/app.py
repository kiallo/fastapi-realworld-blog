import logging
import sys
from typing import Optional
from pydantic import SecretStr, PostgresDsn
from loguru import logger
from app.core.settings.base import BaseAppSettings, AppEnvTypes
from app.core.logging import setup_logging


class AppSettings(BaseAppSettings):
    """应用配置 — 所有环境通用 + 各自覆盖"""

    # ===== FastAPI 基础配置 =====
    debug: bool = True
    docs_url: str = "/docs"
    openapi_prefix: str = ""
    openapi_url: str = "/openapi.json"
    redoc_url: str = "/redoc"
    title: str = "RealWorld Blog API"
    version: str = "0.1.0"

    # ===== 数据库配置 =====
    database_url: PostgresDsn = "postgresql://postgres:postgres@localhost:5432/postgres" # type: ignore

    # 启动时连不上数据库怎么办？
    # False（开发）：打条警告照样启动 —— 数据库没开也能看 Swagger
    # True （生产）：直接抛异常退出（fail fast）—— 宁可起不来，
    #               也不要带着一个坏掉的依赖假装健康（见第 9 部分问题 ⑤）
    db_fail_fast: bool = False

    # ===== Redis 配置 =====
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None  # 如果 Redis 设置了密码

    # ===== JWT 认证配置 =====
    secret_key: SecretStr = SecretStr("dev-secret-key-change-in-production")
    jwt_token_prefix: str = "Token"
    access_token_expire_minutes: int = 60 * 24 * 7  # 一周

    # ===== 日志配置 =====
    logging_level: int = logging.INFO
    loggers: tuple[str, ...] = ("uvicorn", "uvicorn.error", "uvicorn.access")

    # ===== 组合属性 — 不存 .env，由其他字段计算得出 =====

    @property
    def fastapi_kwargs(self) -> dict:
        """生成 FastAPI() 初始化参数，实现环境和框架解耦"""
        return {
            "debug": self.debug,
            "docs_url": self.docs_url,
            "title": self.title,
            "version": self.version,
        }

    def configure_logging(self) -> None:
        """配置日志 — 使用 InterceptHandler 统一接管"""
        setup_logging(
            log_level=self.logging_level,
            loggers=self.loggers,
        )


class DevAppSettings(AppSettings):
    """开发环境配置"""
    debug: bool = True
    title: str = "RealWorld Blog API [DEV]"
    logging_level: int = logging.DEBUG


class ProdAppSettings(AppSettings):
    """生产环境配置"""
    debug: bool = False
    title: str = "RealWorld Blog API"
    logging_level: int = logging.WARNING
    # 生产环境必须通过环境变量设置 secret_key 和 database_url！
    db_fail_fast: bool = True  # 连不上数据库就别启动，交给编排系统重启


class TestAppSettings(AppSettings):
    """测试环境配置"""
    debug: bool = True
    title: str = "RealWorld Blog API [TEST]"
    database_url: PostgresDsn = "postgresql://test:test@test-db:5432/test" # type: ignore
    secret_key: SecretStr = SecretStr("test-secret-key")
    logging_level: int = logging.DEBUG
