from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from app.core.config import get_app_settings
from app.api.dependencies.database import get_repository
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.articles import (
    get_slug_for_article,
    get_article_by_slug_from_path,
    check_article_modification_permissions,
)
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.users import UserInDB
from app.models.domain.articles import Article
from app.models.schemas.articles import (
    ArticleInCreate, ArticleInUpdate, ArticleForResponse,
    ArticleInResponse, ArticlesListInResponse, ArticlesFilters,
)

router = APIRouter(
    prefix="/articles",
    tags=["articles"],
)


@router.get("", response_model=ArticlesListInResponse)
async def list_articles(
    filters: ArticlesFilters = Depends(),
    user: Optional[UserInDB] = Depends(get_current_user_authorizer(required=False)),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
):
    """
    文章列表 — 支持多维度过滤

    过滤器：
    - ?tag=python      → 按标签
    - ?author=alice    → 按作者
    - ?favorited=bob   → 按收藏者
    - ?limit=20&offset=0 → 分页
    """
    # 这里简化处理，完整的动态查询在第 15 课的 pypika 中已实现
    articles: List[Article] = []  # TODO: 接入 pypika 动态查询
    count = 0

    return ArticlesListInResponse(
        articles=[],  # TODO
        articlesCount=count,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ArticleInResponse)
async def create_article(
    article_create: ArticleInCreate,
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
):
    """创建文章"""
    slug = get_slug_for_article(article_create.title)

    article = await articles_repo.create_article(
        slug=slug,
        title=article_create.title,
        description=article_create.description,
        body=article_create.body,
        author=current_user,
        tags=article_create.tag_list,
    )

    return ArticleInResponse(
        article=ArticleForResponse(
            slug=article.slug,
            title=article.title,
            description=article.description,
            body=article.body,
            tagList=article.tags,
            createdAt=article.created_at.isoformat() if hasattr(article.created_at, 'isoformat') else str(article.created_at), # type: ignore
            updatedAt=article.updated_at.isoformat() if hasattr(article.updated_at, 'isoformat') else str(article.updated_at), # type: ignore
            favorited=False,
            favoritesCount=0,
            author={
                "username": current_user.username,
                "bio": current_user.bio,
                "image": current_user.image,
                "following": False,
            },
        )
    )


@router.get("/{slug}", response_model=ArticleInResponse)
async def get_article(
    article: Article = Depends(get_article_by_slug_from_path),
):
    """获取单篇文章"""
    return ArticleInResponse(
        article=ArticleForResponse(
            slug=article.slug,
            title=article.title,
            description=article.description,
            body=article.body,
            tagList=article.tags,
            createdAt=str(article.created_at), # type: ignore
            updatedAt=str(article.updated_at), # type: ignore
            favorited=False,
            favoritesCount=0,
            author=article.author if isinstance(article.author, dict) else {},
        )
    )


@router.put("/{slug}", response_model=ArticleInResponse)
async def update_article(
    article_update: ArticleInUpdate,
    article: Article = Depends(get_article_by_slug_from_path),
    _=Depends(check_article_modification_permissions),
):
    """更新文章 — 只有作者能修改"""
    # TODO: 实现更新逻辑
    return ArticleInResponse(article=ArticleForResponse(
        slug=article.slug, title=article.title,
        description=article.description, body=article.body,
        tagList=article.tags, createdAt=str(article.created_at),    # type: ignore
        updatedAt=str(article.updated_at), favorited=False,         # type: ignore
        favoritesCount=0, author={},
    ))


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_article(
    article: Article = Depends(get_article_by_slug_from_path),
    _=Depends(check_article_modification_permissions),
):
    """删除文章 — 只有作者能删除"""
    # TODO: 实现删除逻辑
    return None


@router.get("/feed", response_model=ArticlesListInResponse)
async def articles_feed(
    filters: ArticlesFilters = Depends(),
    current_user: UserInDB = Depends(get_current_user_authorizer()),
):
    """
    关注 Feed — 你关注的人发布的最新文章

    SQL 逻辑（伪代码）：
    SELECT * FROM articles
    WHERE author_id IN (
        SELECT following_id FROM followers WHERE follower_id = :my_id
    )
    ORDER BY created_at DESC
    LIMIT :limit OFFSET :offset
    """
    # TODO: 接入完整的 Feed 查询
    return ArticlesListInResponse(articles=[], articlesCount=0)