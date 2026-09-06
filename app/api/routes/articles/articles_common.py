from fastapi import APIRouter, Depends, HTTPException, Response
from starlette import status

from app.api.dependencies.articles import get_article_by_slug_from_path
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.database import get_repository
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.articles import Article
from app.models.domain.users import User
from app.models.schemas.articles import ArticleForResponse, ArticleInResponse
from app.resources import strings

router = APIRouter()


def _article_to_response(article: Article) -> ArticleForResponse:
    """Article 领域对象 → 响应 Schema"""
    from app.models.schemas.profiles import ProfileForResponse

    return ArticleForResponse(
        slug=article.slug,
        title=article.title,
        description=article.description,
        body=article.body,
        tag_list=article.tags,
        created_at=str(article.created_at),
        updated_at=str(article.updated_at),
        favorited=article.favorited,
        favorites_count=article.favorites_count,
        author=ProfileForResponse(
            username=article.author.username,
            bio=article.author.bio,
            image=article.author.image,
            following=article.author.following,
        ),
    )


@router.post("/{slug}/favorite", response_model=ArticleInResponse, name="articles:mark-favorite")
async def favorite_article(
    article: Article = Depends(get_article_by_slug_from_path),
    current_user: User = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticleInResponse:
    """收藏文章"""
    if article.favorited:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strings.ALREADY_FAVORITED,
        )

    await articles_repo.add_article_into_favorites(article=article, user=current_user)

    return ArticleInResponse(
        article=_article_to_response(
            article.model_copy(update={
                "favorited": True,
                "favorites_count": article.favorites_count + 1,
            })
        )
    )


@router.delete("/{slug}/favorite", response_model=ArticleInResponse, name="articles:unmark-favorite")
async def unfavorite_article(
    article: Article = Depends(get_article_by_slug_from_path),
    current_user: User = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticleInResponse:
    """取消收藏"""
    if not article.favorited:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strings.ARTICLE_IS_NOT_FAVORITED,
        )

    await articles_repo.remove_article_from_favorites(article=article, user=current_user)

    return ArticleInResponse(
        article=_article_to_response(
            article.model_copy(update={
                "favorited": False,
                "favorites_count": article.favorites_count - 1,
            })
        )
    )
