"""请求级观测：一个请求 → 一个 request_id → 一次指标记录。

为什么不用 BaseHTTPMiddleware：
  1. 它把下游放进 anyio task，loguru 的 contextvar 能不能传下去取决于版本；
     纯 ASGI 中间件和 endpoint 同一个 task，一定传得到。
  2. 每请求少一次 Request/Response 包装 + 一层 task group。
  3. 拿不到响应体（本课不需要，但要清楚这个代价）。
"""

import time
import uuid
from typing import Any, Awaitable, Callable, MutableMapping

from loguru import logger
from starlette.datastructures import MutableHeaders

from app.core.metrics import (
    HTTP_IN_FLIGHT,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

# 没有匹配到任何路由时用的标签值。
# 注意：不要用真实路径兜底 —— 那正是"基数爆炸"的来源（见 4.3）。
UNMATCHED_PATH = "__unmatched__"

# 超过这个耗时就单独打一条 WARNING。原来硬编码在 TimingMiddleware 里是 1.0 秒，
# 而你的 P95 才 100 多毫秒 —— 等于永远不报警。
SLOW_REQUEST_SECONDS = 0.3


class ObservabilityMiddleware:
    """纯 ASGI 中间件：生成 request_id、记录指标、标记慢请求。"""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # WebSocket / lifespan 不走 HTTP 那套指标，直接放行。
        # 项目里有 demo 的 websocket 路由，不判断这一行会抛 KeyError。
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Prometheus 每 5~15 秒抓一次 /metrics。如果把它自己也算进指标，
        # QPS 会凭空多出 0.07~0.2，小时级别的图上看不出来，放大到 1 秒的 rate 就是噪声。
        if scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        # scope["state"] 就是 Request.state 背后的 dict。
        # 用 setdefault：老版本 Starlette 不保证这个键一定存在。
        scope.setdefault("state", {})["request_id"] = request_id

        # 默认 500：如果下游抛异常、一个字节都没发出去，就是 500。
        # 有这个默认值，才不需要在 except 里重复赋值。
        status_code = 500
        started = time.perf_counter()
        HTTP_IN_FLIGHT.inc()

        async def send_with_header(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # 把 ID 回给客户端 —— 用户报障时能直接把这条 ID 给你
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            # 这个 with 覆盖整条下游调用链。
            # endpoint / service / repository 里任何 logger.info() 都会自动带上 request_id，
            # 不用改任何一行业务代码。
            with logger.contextualize(request_id=request_id):
                await self.app(scope, receive, send_with_header)
        except Exception:
            # 交给最外层的 ServerErrorMiddleware 变成 500 响应。
            # 这里只记状态码，不吞异常 —— 吞了就没有 500 页面了。
            status_code = 500
            raise
        finally:
            elapsed = time.perf_counter() - started
            HTTP_IN_FLIGHT.dec()

            # ★ 标签用"路由模板"，不是原始 URL。
            #   /api/articles/post-1 和 /api/articles/post-2 是两条不同的 label 值，
            #   一天就能长出几千条时序，Prometheus 直接 OOM。
            #   FastAPI 的 APIRoute.matches() 会把路由对象写进 child_scope["route"]，
            #   所以这里能拿到模板 /api/articles/{slug}。
            route = scope.get("route")
            path_label = getattr(route, "path", None) or UNMATCHED_PATH
            method = scope.get("method", "UNKNOWN")
            status_label = str(status_code)

            HTTP_REQUESTS_TOTAL.labels(method, path_label, status_label).inc()
            HTTP_REQUEST_DURATION.labels(method, path_label, status_label).observe(elapsed)

            if elapsed >= SLOW_REQUEST_SECONDS:
                # 这条日志带 request_id（在 contextualize 里吗？不在——finally 已经出了 with）。
                # 所以显式 bind，保证慢请求日志自己就能被检索到。
                logger.bind(request_id=request_id).warning(
                    f"慢请求 {method} {path_label} → {status_label} {elapsed * 1000:.0f}ms"
                )
