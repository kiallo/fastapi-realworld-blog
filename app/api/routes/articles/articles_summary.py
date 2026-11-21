import asyncio

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger

from app.api.dependencies.articles import get_article_by_slug_from_path
from app.api.dependencies.authentication import get_current_user_authorizer
from app.core.cache import ArticleCache
from app.core.dependencies import get_redis
from app.core.task_store import SummaryTaskStore
from app.models.domain.articles import Article
from app.models.domain.summary_task import TaskStatus
from app.models.domain.users import UserInDB
from app.models.schemas.summaries import (
    ArticleSummaryContent,
    ArticleSummaryInResponse,
    SummaryTaskInResponse,
)
from app.services.summary import (
    SummaryError,
    SummaryService,
    SummaryTimeoutError,
    get_summary_service,
)
from app.services.summary_tasks import run_summary_task

router = APIRouter()


def _to_response(payload: dict, *, cached: bool) -> ArticleSummaryInResponse:
    return ArticleSummaryInResponse(
        summary=ArticleSummaryContent(**payload["summary"]),
        model=payload["model"],
        cached=cached,
    )


@router.get(
    "/{slug}/summary",
    response_model=ArticleSummaryInResponse,
    name="articles:get-summary",
)
async def get_article_summary(
    article: Article = Depends(get_article_by_slug_from_path),
    redis_client: redis.Redis = Depends(get_redis),
) -> ArticleSummaryInResponse:
    """
    读取文章已有的 AI 摘要（公开接口，任何人可看）

    - 命中缓存：返回摘要，cached=true
    - 没有缓存：404（表示"这篇文章还没生成过摘要"）

    ★ 这里**故意不校验当前用户**：看摘要不该有身份门槛。
      需要保护的是"生成"这个动作（要花钱、要调模型），那条留在下面的 POST 里。
      两个接口共用同一个缓存 key，所以谁先看都一样。
    """
    cache = ArticleCache(redis_client)
    cached = await cache.get_article_summary(article.id)
    if cached is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="这篇文章还没有生成摘要",
        )
    return _to_response(cached, cached=True)


@router.post(
    "/{slug}/summary",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SummaryTaskInResponse,
    name="articles:generate-summary",
)
async def generate_article_summary(
    request: Request,
    article: Article = Depends(get_article_by_slug_from_path),
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    redis_client: redis.Redis = Depends(get_redis),
) -> SummaryTaskInResponse:
    """提交摘要生成任务（202）——立刻返回，活儿在后台干。

    幂等：同一篇文章已有在跑的任务时，返回同一个 task_id，不新建。
    已有缓存时不建任务，直接返回 succeeded。
    """
    if article.author.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有作者可以生成摘要",
        )

    cache = ArticleCache(redis_client)
    store = SummaryTaskStore(redis_client)

    # ① 已有缓存：不建任务，直接给结果（仍然是 202，保持接口语义一致）
    cached = await cache.get_article_summary(article.id)
    if cached is not None:
        return SummaryTaskInResponse(
            task_id=f"cached-{article.id}",
            status="succeeded",
            summary=ArticleSummaryContent(**cached["summary"]),
            model=cached["model"],
        )

    # ② 幂等：已有在跑的任务，返回它
    active_id = await store.get_active_task_id(article.id)
    if active_id:
        existing = await store.get(active_id)
        if existing is not None and existing.status in (
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
        ):
            return SummaryTaskInResponse(
                task_id=existing.task_id,
                status=existing.status.value,
            )

    # ③ 抢键 → 建任务 → 丢后台
    service: SummaryService = get_summary_service(request)
    task = await store.create(article_id=article.id)

    if not await store.bind_active(article.id, task.task_id):
        # 抢输了：另一个请求刚好抢先，返回它的任务
        winner_id = await store.get_active_task_id(article.id)
        winner = await store.get(winner_id) if winner_id else None
        if winner is not None:
            return SummaryTaskInResponse(task_id=winner.task_id, status=winner.status.value)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="摘要任务提交冲突，请重试",
        )

    asyncio.create_task(
        run_summary_task(
            task_id=task.task_id,
            article_id=article.id,
            title=article.title,
            body=article.body,
            store=store,
            cache=cache,
            service=service,
            redis_client=redis_client,
        )
    )
    return SummaryTaskInResponse(task_id=task.task_id, status=task.status.value)


@router.get(
    "/{slug}/summary/tasks/{task_id}",
    response_model=SummaryTaskInResponse,
    name="articles:get-summary-task",
)
async def get_summary_task(
    task_id: str,
    article: Article = Depends(get_article_by_slug_from_path),
    redis_client: redis.Redis = Depends(get_redis),
) -> SummaryTaskInResponse:
    """轮询任务状态。公开接口：知道 task_id 就能查（它不可猜，32 位 hex）。"""
    store = SummaryTaskStore(redis_client)
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或已过期")
    if task.article_id != article.id:
        # 防止拿 A 文章的 task_id 去查 B 文章的路径
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或已过期")

    payload = None
    if task.status is TaskStatus.SUCCEEDED:
        cache = ArticleCache(redis_client)
        cached = await cache.get_article_summary(article.id)
        payload = ArticleSummaryContent(**cached["summary"]) if cached else None

    return SummaryTaskInResponse(
        task_id=task.task_id,
        status=task.status.value,
        summary=payload,
        error=task.error,
    )
