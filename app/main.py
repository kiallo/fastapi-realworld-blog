from fastapi import FastAPI
from app.api.routes.api import router as api_router

app = FastAPI(
    title="RealWorld Blog API",
    description="一个符合 RealWorld 规范的博客 API — 从零构建",
    version="0.1.0",
)

# 挂载主路由（所有 API 端点统一以 /api 开头）
app.include_router(api_router)