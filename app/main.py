from fastapi import FastAPI
from app.api.routes.api import router as api_router
from app.core.config import get_app_settings

# 获取配置（第一次调用，创建并缓存）
settings = get_app_settings()

# 用配置生成 FastAPI 实例
app = FastAPI(**settings.fastapi_kwargs)

# 挂载主路由（所有 API 端点统一以 /api 开头）
app.include_router(api_router)