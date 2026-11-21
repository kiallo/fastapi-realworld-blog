"""摘要任务的后台执行器。

只做四件事：改状态 → 调 LLM（带重试）→ 写缓存 → 收尾。
注意：它跑在 asyncio 的后台任务里，异常不会冒到 HTTP 层，必须自己兜住。
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Awaitable, Optional, cast

import redis.asyncio as redis
from loguru import logger

from app.core.cache import ArticleCache
from app.core.metrics import (
    SUMMARY_TASK_DURATION,
    SUMMARY_TASK_RETRIES,
    SUMMARY_TASKS_TOTAL,
)
from app.core.task_store import SummaryTaskStore
from app.models.domain.summary_task import TaskStatus
from app.services.summary import SummaryError, SummaryService

MAX_ATTEMPTS = 2  # 首次 + 1 次重试
RETRY_BACKOFF_SECONDS = 1.0
DEAD_LETTER_KEY = "summary:dead"
DEAD_LETTER_MAX = 1000


async def run_summary_task(
    *,
    task_id: str,
    article_id: int,
    title: str,
    body: str,
    store: SummaryTaskStore,
    cache: ArticleCache,
    service: SummaryService,
    redis_client: redis.Redis,
) -> None:
    """后台跑一次摘要任务。任何异常都必须落到 failed，不能静默丢弃。"""
    task = await store.get(task_id)
    if task is None:  # TTL 过期或 key 被清
        logger.warning(f"任务不存在，跳过 task_id={task_id}")
        return

    await store.set_status(task, TaskStatus.RUNNING)
    started = time.perf_counter()

    try:
        last_error: Optional[str] = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                content, usage = await service.generate(title=title, body=body)
            except SummaryError as exc:
                last_error = str(exc)
                await store.set_status(task, TaskStatus.RUNNING, attempts=attempt)
                if attempt < MAX_ATTEMPTS:
                    SUMMARY_TASK_RETRIES.inc()
                    logger.warning(f"摘要任务重试 task_id={task_id} attempt={attempt}: {exc}")
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                break  # 重试耗尽，走下面的 failed 分支

            payload = {
                "summary": content.model_dump(),
                "model": service.model,
                "usage": usage,
            }
            await cache.set_article_summary(article_id, payload)
            await store.set_status(task, TaskStatus.SUCCEEDED, attempts=attempt)
            SUMMARY_TASKS_TOTAL.labels(status=TaskStatus.SUCCEEDED.value).inc()
            logger.info(f"摘要任务成功 task_id={task_id} article_id={article_id} attempt={attempt}")
            return

        # 走到这里 = 重试耗尽
        await store.set_status(task, TaskStatus.FAILED, error=last_error, attempts=MAX_ATTEMPTS)
        SUMMARY_TASKS_TOTAL.labels(status=TaskStatus.FAILED.value).inc()
        await _push_dead_letter(
            redis_client,
            {"task_id": task_id, "article_id": article_id, "error": last_error},
        )
        logger.error(f"摘要任务失败 task_id={task_id} error={last_error}")

    except Exception as exc:  # 兜底：连 Redis 都写不进去时至少留日志
        logger.exception(f"摘要任务异常 task_id={task_id}: {exc}")
        try:
            await store.set_status(task, TaskStatus.FAILED, error=f"内部错误: {exc}")
            SUMMARY_TASKS_TOTAL.labels(status=TaskStatus.FAILED.value).inc()
        except Exception:
            pass
    finally:
        SUMMARY_TASK_DURATION.observe(time.perf_counter() - started)
        await store.release_active(article_id, task_id)


async def _push_dead_letter(redis_client: redis.Redis, payload: dict) -> None:
    """失败任务单独存一份，方便人工重放；只留最近 1000 条。"""
    try:
        record = dict(payload, failed_at=datetime.now(timezone.utc).isoformat())
        # 与 task_store 同理：redis-py 把命令签名标成 Union[Awaitable[T], T]，
        # 静态检查器不认 await，cast 只做类型收窄。
        await cast(
            "Awaitable[int]",
            redis_client.lpush(DEAD_LETTER_KEY, json.dumps(record, ensure_ascii=False)),
        )
        await cast("Awaitable[str]", redis_client.ltrim(DEAD_LETTER_KEY, 0, DEAD_LETTER_MAX - 1))
    except Exception as exc:
        logger.warning(f"写死信失败: {exc}")
