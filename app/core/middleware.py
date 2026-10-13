import time
import uuid
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

    ⚠️ 中间件栈的顺序是"反的"：
    main.py 里的添加顺序是 CORS → Timing → Logging，
    但 Starlette 的 add_middleware 是 insert(0)，**后加的在最外层**，
    所以实际执行顺序是：

    Request  → [Logging] → [Timing] → [CORS] → [Router] → [视图函数]
    Response ← [Logging] ← [Timing] ← [CORS] ← [Router] ← [视图函数]
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


class LoggingMiddleware(BaseHTTPMiddleware):
    """详细日志记录中间件"""
    
    async def dispatch(self, request: Request, call_next):
        # 生成请求ID（用于追踪）
        request_id = str(uuid.uuid4())[:8]

        # 如果是POST/PUT请求，记录请求体（注意性能）
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    logger.info(f"   Body: {body.decode('utf-8')[:500]}")  # 限制长度
            except:
                pass

        # 处理请求
        start_time = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start_time

        # 记录响应
        logger.info(f"🟢 [{request_id}] {response.status_code} ({elapsed:.3f}s)")

        # 添加自定义响应头
        # ⚠️ X-Process-Time 归 TimingMiddleware 管 —— 这里不要再写一次。
        #    本中间件在最外层，响应回流是"内层先写、外层后写"，
        #    再写一次会把 Timing 的值覆盖掉，造成"改了一个中间件、值却是另一个算的"。
        response.headers["X-Request-ID"] = request_id

        return response