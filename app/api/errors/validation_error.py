from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def http422_error_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    统一参数校验错误响应格式

    将 Pydantic 的校验错误（422）转换为 RealWorld 规范：
    {
        "errors": {
            "body": ["字段 'email' 不能为空", "字段 'password' 长度不足"]
        }
    }
    """
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        msg = error["msg"]
        errors.append(f"{field}: {msg}" if field else msg)

    return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"errors": {"body": errors}},
        )