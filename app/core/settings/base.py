from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvTypes(str, Enum):
    """应用环境类型"""
    prod = "prod"
    dev = "dev"
    test = "test"

class BaseAppSettings(BaseSettings):
    """所有环境共享的基础配置"""

    app_env: AppEnvTypes = AppEnvTypes.dev

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # 可选：env_prefix="APP_"   # 如果你想统一前缀，可以用这个
    )