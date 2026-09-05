from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


async def http_error_handler(
    _: Request,
    exc: HTTPException,
) -> JSONResponse:
    """
    统一 HTTP 异常响应格式

    将 FastAPI 默认的 {"detail": "..."} 格式
    转换为 RealWorld API 规范：{"errors": {"body": ["..."]}}
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"errors": {"body": [exc.detail]}},
    )