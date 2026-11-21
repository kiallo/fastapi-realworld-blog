"""摘要任务 — 状态机与数据形状。

存在 Redis hash 里，TTL 1 小时；不落 PostgreSQL（理由见第 29 课 1.3）。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态 — 只允许这四个值"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SummaryTask(BaseModel):
    """一个摘要任务的全部字段。

    Redis hash 的字段名和这里一一对应，靠 model_dump() 写入、**row 读出。
    """

    task_id: str
    article_id: int
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0                     # 已尝试次数（含首次）
    error: Optional[str] = None           # 失败原因（只给 failed 用）
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)