import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger

from app.api.dependencies.articles import get_article_by_slug_from_path
from app.api.dependencies.authentication import get_current_user_authorizer
from app.core.cache import ArticleCache
from app.core.dependencies import get_redis
from app.models.domain.articles import Article
from app.models.domain.users import UserInDB
from app.models.schemas.summaries import (
    ArticleSummaryContent,
    ArticleSummaryInResponse,
)
from app.services.summary import (
    SummaryError,
    SummaryService,
    SummaryTimeoutError,
    get_summary_service,
)

router = APIRouter()


def _to_response(payload: dict, *, cached: bool) -> ArticleSummaryInResponse:
    return ArticleSummaryInResponse(
        summary=ArticleSummaryContent(**payload["summary"]),
        model=payload["model"],
        cached=cached,
    )


@router.post(
    "/{slug}/summary",
    response_model=ArticleSummaryInResponse,
    name="articles:generate-summary",
)
async def generate_article_summary(
    request: Request,
    article: Article = Depends(get_article_by_slug_from_path),
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    redis_client: redis.Redis = Depends(get_redis),
) -> ArticleSummaryInResponse:
    """
    为文章生成 AI 摘要（仅作者可触发）

    - 已有缓存：直接返回，cached=true
    - 没有缓存：加 Redis 锁，调 LLM，写缓存
    - 并发请求：拿不到锁返回 409
    - LLM 超时：504
    - LLM 其他失败：503
    """
    if article.author.username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有作者可以生成摘要",
        )

    cache = ArticleCache(redis_client)

    cached = await cache.get_article_summary(article.id)
    if cached is not None:
        return _to_response(cached, cached=True)

    # 缓存未命中才需要 LLM；没配置时返回 503，不影响已缓存摘要
    summary_service: SummaryService = get_summary_service(request)

    lock_key = f"summary:lock:{article.id}"
    acquired = await redis_client.set(lock_key, "1", nx=True, ex=60)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="摘要正在生成中，请稍后重试",
        )

    try:
        content, usage = await summary_service.generate(
            title=article.title,
            body=article.body,
        )

        payload = {
            "summary": content.model_dump(),
            "model": summary_service.model,
            "usage": usage,
        }
        await cache.set_article_summary(article.id, payload)

        logger.info(
            f"摘要接口完成 article_id={article.id} "
            f"model={summary_service.model} cached=false"
        )
        return _to_response(payload, cached=False)

    except SummaryTimeoutError as exc:
        logger.warning(f"摘要超时 article_id={article.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="摘要生成超时，请稍后重试",
        ) from exc
    except SummaryError as exc:
        logger.error(f"摘要失败 article_id={article.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="摘要生成失败，请稍后重试",
        ) from exc
    finally:
        try:
            await redis_client.delete(lock_key)
        except Exception as e:
            logger.warning(f"释放摘要锁失败: {e}")