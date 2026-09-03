"""文章收藏/取消收藏 + Feed"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies.database import get_repository
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.articles import get_article_by_slug_from_path
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.users import UserInDB
from app.models.domain.articles import Article
from app.models.schemas.articles import (
    ArticleForResponse, ArticleInResponse, ArticlesListInResponse,
    ArticlesFilters,
)
from app.db.queries.queries import queries

router = APIRouter()


def _build_article_response(article: Article, author: dict, favorited: bool, favorites_count: int) -> ArticleInResponse:
    return ArticleInResponse(
        article=ArticleForResponse(
            slug=article.slug,
            title=article.title,
            description=article.description,
            body=article.body,
            tagList=article.tags,
            createdAt=str(article.created_at), # type: ignore
            updatedAt=str(article.updated_at), # type: ignore
            favorited=favorited,
            favoritesCount=favorites_count,
            author=author,
        )
    )


@router.post("/{slug}/favorite", response_model=ArticleInResponse)
async def favorite_article(
    article: Article = Depends(get_article_by_slug_from_path),
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
):
    """收藏文章"""
    # 检查是否已收藏
    already_favorited = await queries.is_article_favorited( # type: ignore
        articles_repo.connection,
        user_id=current_user.id,
        article_id=article.id,
    )

    if already_favorited and already_favorited.get("favorited"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="你已经收藏过这篇文章",
        )

    # 写入收藏
    await queries.add_to_favorites( # type: ignore
        articles_repo.connection,
        user_id=current_user.id,
        article_id=article.id,
    )

    return _build_article_response(
        article,
        author={"username": current_user.username, "bio": current_user.bio, "image": current_user.image, "following": False},
        favorited=True,
        favorites_count=1,  # TODO: 准确计数
    )


@router.delete("/{slug}/favorite", response_model=ArticleInResponse)
async def unfavorite_article(
    article: Article = Depends(get_article_by_slug_from_path),
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
):
    """取消收藏"""
    await queries.remove_from_favorites( # type: ignore
        articles_repo.connection,
        user_id=current_user.id,
        article_id=article.id,
    )

    return _build_article_response(
        article,
        author={"username": current_user.username, "bio": current_user.bio, "image": current_user.image, "following": False},
        favorited=False,
        favorites_count=0,
    )