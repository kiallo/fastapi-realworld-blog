from functools import lru_cache
from app.core.settings.app import (
    AppSettings,
    DevAppSettings,
    ProdAppSettings,
    TestAppSettings,
)
from app.core.settings.base import AppEnvTypes, BaseAppSettings

# 环境 → 配置类的映射表
environments: dict[AppEnvTypes, type[AppSettings]] = {
    AppEnvTypes.dev: DevAppSettings,
    AppEnvTypes.prod: ProdAppSettings,
    AppEnvTypes.test: TestAppSettings,
}


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """
    配置单例工厂 — 全应用只实例化一次

    @lru_cache 的作用：
      第一次调用 → 创建 DevAppSettings() → 缓存
      第二次调用 → 直接返回缓存的实例
      第 N 次调用 → 同上，不会重复创建
    """
    # 从环境变量 APP_ENV 读取（BaseAppSettings 会读 .env / 系统环境变量），默认 dev
    app_env = BaseAppSettings().app_env
    config_class = environments[app_env]
    return config_class()
