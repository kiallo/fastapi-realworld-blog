from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.api import router as api_router
from app.core.config import get_app_settings
from app.core.events import create_start_app_handler, create_stop_app_handler

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

    # ③ 创建 FastAPI 实例
    application = FastAPI(**settings.fastapi_kwargs)

    # ④ 添加中间件（CORS — 允许跨域请求）
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],           # 开发阶段允许所有来源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ⑤ 注册启停事件（预留 — 第 8 课填充数据库连接逻辑）
    application.add_event_handler("startup", create_start_app_handler(application))
    application.add_event_handler("shutdown", create_stop_app_handler(application))

    # ⑥ 注册异常处理器（预留 — 第 28 课填充）
    # application.add_exception_handler(HTTPException, ...)

    # ⑦ 挂载路由
    application.include_router(api_router)

    return application

# uvicorn 入口：uvicorn app.main:app
app = get_application()