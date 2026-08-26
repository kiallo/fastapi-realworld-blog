"""
文章列表的动态查询构建

为什么要用 pypika 而不是 aiosql？
— aiosql 只能写静态 SQL，无法根据参数动态添加 JOIN 和 WHERE
— 文章列表 API 支持 3 种可选过滤（tag/author/favorited），组合出 8 种 SQL
— 手写 8 种 SQL → 用 pypika 动态构建 → 1 个函数搞定
"""
from typing import Optional
from pypika import Query, JoinType, Order
from pypika.functions import Count
from app.db.queries.tables import (
    articles, users, tags, articles_to_tags, favorites, followers,
)


def build_filter_articles_query(
    tag: Optional[str] = None,
    author: Optional[str] = None,
    favorited: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[str, list]:
    """
    构建文章列表查询

    返回：SQL 字符串
    """
    # 基础 SELECT
    query = Query.from_(articles).select(
        articles.id, articles.slug, articles.title,
        articles.description, articles.body,
        articles.author_id, articles.created_at, articles.updated_at,
    ).distinct()

    # 根据过滤条件动态 JOIN
    params = []

    if tag:
        query = query.join(articles_to_tags).on(
            articles_to_tags.article_id == articles.id # type: ignore
        )
        query = query.where(articles_to_tags.tag == tag) # type: ignore

    if author:
        # 子查询：找到目标作者的用户 ID
        query = query.where(
            articles.author_id == Query.from_(users) # type: ignore
                .select(users.id)
                .where(users.username == author)    # type: ignore
        )

    if favorited:
        query = query.join(favorites).on(
            favorites.article_id == articles.id # type: ignore
        )
        query = query.join(users).on(
            favorites.user_id == users.id   # type: ignore
        )
        query = query.where(users.username == favorited)  # type: ignore

    # 排序 + 分页
    query = query.orderby(articles.created_at, order=Order.desc)
    query = query.limit(limit).offset(offset)

    return query.get_sql() # type: ignore


def build_count_articles_query(
    tag: Optional[str] = None,
    author: Optional[str] = None,
    favorited: Optional[str] = None,
) -> tuple[str, list]:
    """构建文章计数查询"""
    query = Query.from_(articles).select(Count("*"))

    if tag:
        query = query.join(articles_to_tags).on(
            articles_to_tags.article_id == articles.id  # type: ignore
        )
        query = query.where(articles_to_tags.tag == tag) # type: ignore

    if author:
        query = query.where(
            articles.author_id == Query.from_(users)
                .select(users.id)
                .where(users.username == author) # type: ignore
        )

    if favorited:
        query = query.join(favorites).on(
            favorites.article_id == articles.id # type: ignore
        )
        query = query.join(users, JoinType.inner).on(
            favorites.user_id == users.id # type: ignore
        )
        query = query.where(users.username == favorited) # type: ignore

    return query.get_sql() # type: ignore