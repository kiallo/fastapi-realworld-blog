from fastapi import Depends, HTTPException, status, Path
from slugify import slugify
import redis.asyncio as redis
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.database import get_repository
from app.core.cache import ArticleCache
from app.core.dependencies import get_redis
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.articles import Article
from app.models.domain.users import UserInDB
from typing import AsyncGenerator, Optional


async def invalidate_articles_cache(
    redis_client: redis.Redis = Depends(get_redis),
) -> AsyncGenerator[None, None]:
    """★ 让写操作在**成功之后**自动清掉文章缓存

    写成依赖是为了不在 5 个写接口里各抄一遍。

    为什么把失效放在 `yield` **之后**：
    FastAPI 的 generator 依赖，yield 之后的代码在响应生成后才执行；
    如果视图函数抛了 HTTPException（比如"已经收藏过了"），
    异常会被抛回 yield 那个点，后面的代码根本不会跑 ——
    所以"只有写成功才清缓存"是天然成立的，不用自己写判断。

    ⚠️ 因为它跑在响应之后：清缓存失败了也不影响这次请求的结果，
    只会让数据多脏一会儿（由 TTL 兜底，列表 5 分钟）。
    """
    yield
    await ArticleCache(redis_client).invalidate_all_articles()


def get_slug_for_article(title: str) -> str:
    """根据标题生成 URL Slug"""
    return slugify(title)


async def get_article_by_slug_from_path(
    slug: str = Path(..., min_length=1),
    articles_repo: ArticlesRepository = Depends(
        get_repository(ArticlesRepository)
    ),
    requested_user: Optional[UserInDB] = Depends(
        get_current_user_authorizer(required=False)
    ), 
) -> Article:
    """从 URL 路径参数中获取文章"""
    try:
        return await articles_repo.get_article_by_slug(
            slug=slug,
            requested_user=requested_user,     
        )
    except Exception:
        raise HTTPException(404, detail=f"文章 {slug} 不存在")


async def check_article_modification_permissions(
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    article: Article = Depends(get_article_by_slug_from_path),
) -> None:
    """检查文章修改权限 — 只有作者本人可以修改"""
    if article.author and article.author.username != current_user.username: 
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="你没有权限修改这篇文章",
        )