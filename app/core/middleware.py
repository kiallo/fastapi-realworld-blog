import time
from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class TimingMiddleware(BaseHTTPMiddleware):
    """
    请求耗时统计中间件

    BaseHTTPMiddleware 的执行模型：
    请求来 → dispatch() 被调用
         ├─ await self.call_next(request)  ← 这里执行真正的业务逻辑
         └─ 拿到 response 后，可以做后处理

    中间件栈：
    Request → [CORS] → [Timing] → [Router] → [你的视图函数]
    Response ← [CORS] ← [Timing] ← [Router] ← [你的视图函数]
    """

    async def dispatch(self, request: Request, call_next):
        # ① 记录开始时间
        start_time = time.monotonic()

        # ② 执行业务逻辑（包括后续中间件、路由匹配、视图函数）
        response = await call_next(request)

        # ③ 计算耗时
        elapsed = time.monotonic() - start_time

        # ④ 记录日志（区分慢请求）
        log_func = logger.warning if elapsed > 1.0 else logger.info
        log_func(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} "
            f"({elapsed:.3f}s){' ⚠️ 慢请求!' if elapsed > 1.0 else ''}"
        )

        # ⑤ 添加响应头（可选 — 让前端也能看到耗时）
        response.headers["X-Process-Time"] = f"{elapsed:.3f}s"

        return response