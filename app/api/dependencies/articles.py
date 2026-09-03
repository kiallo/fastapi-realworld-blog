from fastapi import Depends, HTTPException, status, Path
from slugify import slugify
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.database import get_repository
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.articles import Article
from app.models.domain.users import UserInDB


def get_slug_for_article(title: str) -> str:
    """根据标题生成 URL Slug"""
    return slugify(title)


async def get_article_by_slug_from_path(
    slug: str = Path(..., min_length=1),
    articles_repo: ArticlesRepository = Depends(
        get_repository(ArticlesRepository)
    ),
) -> Article:
    """从 URL 路径参数中获取文章"""
    try:
        return await articles_repo.get_article_by_slug(slug=slug)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文章 {slug} 不存在",
        )


async def check_article_modification_permissions(
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    article: Article = Depends(get_article_by_slug_from_path),
) -> None:
    """检查文章修改权限 — 只有作者本人可以修改"""
    if article.author and article.author.get("username") != current_user.username: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="你没有权限修改这篇文章",
        )