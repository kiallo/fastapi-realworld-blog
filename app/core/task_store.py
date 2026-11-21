"""摘要任务的 Redis 存储 + 幂等键。

key 设计（前缀集中在这里，别处不许拼）：
  summary:task:{task_id}       hash，任务本体，TTL 1 小时
  summary:active:{article_id}  string，指向"正在跑的任务"，TTL 3 分钟
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Optional, cast

import redis.asyncio as redis
from loguru import logger

from app.models.domain.summary_task import SummaryTask, TaskStatus

TASK_TTL_SECONDS = 3600
ACTIVE_TTL_SECONDS = 180

_TASK_KEY = "summary:task:{}"
_ACTIVE_KEY = "summary:active:{}"


class SummaryTaskStore:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    # ---------- 任务本体 ----------

    async def create(self, *, article_id: int) -> SummaryTask:
        task = SummaryTask(task_id=uuid.uuid4().hex, article_id=article_id)
        await self._save(task)
        return task

    async def get(self, task_id: str) -> Optional[SummaryTask]:
        # redis-py 的同步/异步客户端共用命令签名，hgetall/hset 被标成
        # Union[Awaitable[T], T]，静态检查器不认 await；运行时 execute_command
        # 是协程，cast 只是把类型收窄成 Awaitable。
        data = await cast(
            "Awaitable[dict[str, Any]]", self._redis.hgetall(_TASK_KEY.format(task_id))
        )
        if not data:
            return None
        data["article_id"] = int(data["article_id"])
        data["attempts"] = int(data.get("attempts", 0))
        return SummaryTask(**data)

    async def set_status(
        self,
        task: SummaryTask,
        status: TaskStatus,
        *,
        error: Optional[str] = None,
        attempts: Optional[int] = None,
    ) -> None:
        task.status = status
        task.error = error
        if attempts is not None:
            task.attempts = attempts
        task.updated_at = datetime.now(timezone.utc)
        await self._save(task)

    async def _save(self, task: SummaryTask) -> None:
        key = _TASK_KEY.format(task.task_id)
        mapping = {
            "task_id": task.task_id,
            "article_id": str(task.article_id),
            "status": task.status.value,
            "attempts": str(task.attempts),
            "error": task.error or "",
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }
        await cast("Awaitable[int]", self._redis.hset(key, mapping=mapping))
        await self._redis.expire(key, TASK_TTL_SECONDS)

    # ---------- 幂等键 ----------

    async def get_active_task_id(self, article_id: int) -> Optional[str]:
        return await cast(
            "Awaitable[Optional[str]]", self._redis.get(_ACTIVE_KEY.format(article_id))
        )

    async def bind_active(self, article_id: int, task_id: str) -> bool:
        """抢占"这篇文章的进行中任务"；抢到返回 True。

        SET NX 是原子的：10 个并发请求里只有一个能拿到。
        """
        return bool(
            await self._redis.set(
                _ACTIVE_KEY.format(article_id),
                task_id,
                nx=True,
                ex=ACTIVE_TTL_SECONDS,
            )
        )

    async def release_active(self, article_id: int, task_id: str) -> None:
        """只删自己占的那个，别删别人后来占的。"""
        key = _ACTIVE_KEY.format(article_id)
        try:
            current = await self._redis.get(key)
            if current == task_id:
                await self._redis.delete(key)
        except Exception as exc:  # 清理失败不该影响任务结论
            logger.warning(f"释放 active 键失败 article_id={article_id}: {exc}")
