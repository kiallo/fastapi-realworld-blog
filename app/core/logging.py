import logging
import sys
from io import TextIOWrapper
from types import FrameType
from typing import Optional, Union

from loguru import logger


class InterceptHandler(logging.Handler):
    """
    拦截标准库 logging 日志，重定向到 Loguru

    工作原理：
    1. 继承 logging.Handler
    2. 覆写 emit() 方法
    3. 每当标准库 logging 产生一条日志，emit() 被调用
    4. 在 emit() 中，把 logging 日志转换为 Loguru 日志
    """

    def emit(self, record: logging.LogRecord) -> None:
        # ① 把标准库级别名映射为 Loguru 级别（如 "INFO"），避免显示成 "Level 20"
        level: Union[str, int]
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # 自定义级别时回退到数字

        # ② 找到真正产生日志的调用者（跳过 logging 内部帧）
        #    从第 6 帧开始向上回溯，是因为 emit() 被 logging.Handler 链调用，
        #    中间隔着一层层 logging 的内部帧；循环跳过它们，最终停在用户代码。
        frame: Optional[FrameType] = sys._getframe(6)
        depth = 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # ③ 使用 Loguru 输出日志
        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def setup_logging(
    log_level: int,
    loggers: tuple[str, ...],
    json_log_path: Optional[str] = None,
    json_log_level: int = logging.INFO,
) -> None:
    """
    配置全局日志：
    1. 移除 Loguru 默认 handler
    2. 添加自定义格式的 handler
    3. 用 InterceptHandler 接管所有标准库 logger

    参数：
        log_level: 日志级别（如 logging.INFO）
        loggers:  需要接管的 logger 名称元组（如 ("uvicorn", "uvicorn.error", "uvicorn.access")）
    """
    # ① 解决 Windows 控制台 GBK 编码无法输出 emoji 的问题
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8")

    # ② 移除 Loguru 默认 handler
    logger.remove()

    # ② 添加格式化输出
    logger.add(
        sys.stdout,
        level=log_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
    )
    # ② 结构化日志落文件：一行一个 JSON，方便 jq / grep / 后续导入
    #
    #   serialize=True    → {"text": "...", "record": {...}} 一整行 JSON
    #   enqueue=True      → 磁盘写入交给后台线程，不阻塞事件循环。
    #                       压测时这一项差别很明显：同步写文件会把 asyncio 卡住。
    #   diagnose=False    → 异常时不要把局部变量打进日志。
    #                       你的局部变量里有 token、有密码、有 LLM 的 key。
    if json_log_path:
        logger.add(
            json_log_path,
            level=json_log_level,
            serialize=True,
            enqueue=True,
            rotation="10 MB",
            retention="7 days",
            encoding="utf-8",
            backtrace=False,
            diagnose=False,
        )

    # ③ 用 InterceptHandler 接管所有标准库 logger
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for logger_name in loggers:
        _logger = logging.getLogger(logger_name)
        _logger.handlers = [InterceptHandler()]
        _logger.propagate = False
