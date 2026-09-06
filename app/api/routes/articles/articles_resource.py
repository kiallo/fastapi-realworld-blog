from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from starlette import status

from app.api.dependencies.articles import (
    check_article_modification_permissions,
    get_article_by_slug_from_path,
    get_slug_for_article,
)
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.database import get_repository
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.articles import Article
from app.models.domain.users import User
from app.models.schemas.articles import (
    ArticleForResponse,
    ArticleInCreate,
    ArticleInResponse,
    ArticleInUpdate,
    ArticlesFilters,
    ArticlesListInResponse,
)
from app.resources import strings
from app.services.articles import check_article_exists

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


@router.get("", response_model=ArticlesListInResponse, name="articles:list-articles")
async def list_articles(
    filters: ArticlesFilters = Depends(),
    user: Optional[User] = Depends(get_current_user_authorizer(required=False)),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticlesListInResponse:
    """文章列表 — 支持多维度过滤（tag/author/favorited）"""
    articles = await articles_repo.filter_articles(
        tag=filters.tag,
        author=filters.author,
        favorited=filters.favorited,
        limit=filters.limit,
        offset=filters.offset,
        requested_user=user,
    )
    return ArticlesListInResponse(
        articles=[_article_to_response(a) for a in articles],
        articlesCount=len(articles),
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ArticleInResponse, name="articles:create-article")
async def create_article(
    article_create: ArticleInCreate = Body(..., embed=True, alias="article"),
    current_user: User = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticleInResponse:
    """创建文章"""
    slug = get_slug_for_article(article_create.title)

    if await check_article_exists(articles_repo, slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strings.ARTICLE_ALREADY_EXISTS,
        )

    article = await articles_repo.create_article(
        slug=slug,
        title=article_create.title,
        description=article_create.description,
        body=article_create.body,
        author=current_user,
        tags=article_create.tag_list,
    )
    return ArticleInResponse(article=_article_to_response(article))


@router.get("/feed", response_model=ArticlesListInResponse, name="articles:user-feed")
async def articles_feed(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticlesListInResponse:
    """关注 Feed — 你关注的人发布的最新文章"""
    articles = await articles_repo.get_articles_for_user_feed(
        user=current_user,
        limit=limit,
        offset=offset,
    )
    return ArticlesListInResponse(
        articles=[_article_to_response(a) for a in articles],
        articlesCount=len(articles),
    )


@router.get("/{slug}", response_model=ArticleInResponse, name="articles:get-article")
async def get_article(
    article: Article = Depends(get_article_by_slug_from_path),
) -> ArticleInResponse:
    """获取单篇文章"""
    return ArticleInResponse(article=_article_to_response(article))


@router.put("/{slug}", response_model=ArticleInResponse, name="articles:update-article")
async def update_article(
    article_update: ArticleInUpdate = Body(..., embed=True, alias="article"),
    article: Article = Depends(get_article_by_slug_from_path),
    _=Depends(check_article_modification_permissions),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticleInResponse:
    """更新文章 — 只有作者可以修改"""
    updated = await articles_repo.update_article(
        article=article,
        slug=get_slug_for_article(article_update.title) if article_update.title else None,
        title=article_update.title,
        body=article_update.body,
        description=article_update.description,
    )
    return ArticleInResponse(article=_article_to_response(updated))


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT, name="articles:delete-article", response_class=Response)
async def delete_article(
    article: Article = Depends(get_article_by_slug_from_path),
    _=Depends(check_article_modification_permissions),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> None:
    """删除文章 — 只有作者可以删除"""
    await articles_repo.delete_article(article=article)
