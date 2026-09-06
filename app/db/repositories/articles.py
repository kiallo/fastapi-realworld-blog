from typing import List, Optional, Sequence, Union

from asyncpg import Connection
from pypika import Query, Order

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.queries.tables import (
    AsyncpgParameter,
    articles as articles_table,
    articles_to_tags,
    favorites,
    tags as tags_table,
    users as users_table,
)
from app.db.repositories.base import BaseRepository
from app.db.repositories.profiles import ProfilesRepository
from app.db.repositories.tags import TagsRepository
from app.models.domain.articles import Article
from app.models.domain.users import User


DEFAULT_ARTICLES_LIMIT = 20
DEFAULT_ARTICLES_OFFSET = 0


class ArticlesRepository(BaseRepository):
    def __init__(self, conn: Connection) -> None:
        super().__init__(conn)
        self._profiles_repo = ProfilesRepository(conn)
        self._tags_repo = TagsRepository(conn)

    async def create_article(
        self, *, slug: str, title: str, description: str,
        body: str, author: User, tags: Optional[Sequence[str]] = None,
    ) -> Article:
        """创建文章 + 标签关联 — 整个操作在事务中完成"""
        async with self.connection.transaction():
            # 步骤 1：创建文章
            row = await queries.create_article(  # type: ignore
                self.connection,
                slug=slug,
                title=title,
                description=description,
                body=body,
                author_id=author.id if hasattr(author, 'id') else None,
            )

            # 步骤 2：创建不存在的标签
            if tags:
                await self._tags_repo.create_tags_that_dont_exist(tags=tags)

                # 步骤 3：关联标签
                await self._tags_repo.link_article_with_tags(
                    article_id=row["id"], tags=list(tags)
                )

        # 任何步骤失败 → 自动回滚 → 数据库没有任何变化
        return await self._build_article_from_row(row, requested_user=author)


    async def get_article_by_slug(
        self, *, slug: str, requested_user: Optional[User] = None,
    ) -> Article:
        """通过 slug 获取文章"""
        row = await queries.get_article_by_slug(self.connection, slug=slug)  # type: ignore
        if row is None:
            raise EntityDoesNotExist(f"文章 {slug} 不存在")
        return await self._build_article_from_row(row, requested_user=requested_user)

    async def update_article(
        self, *, article: Article, slug: Optional[str] = None,
        title: Optional[str] = None, body: Optional[str] = None,
        description: Optional[str] = None, **kwargs,
    ) -> Article:
        """更新文章"""
        updated = article.model_copy(deep=True)
        updated.slug = slug or updated.slug
        updated.title = title or updated.title
        updated.body = body or updated.body
        updated.description = description or updated.description

        async with self.connection.transaction():
            result = await queries.update_article(  # type: ignore
                self.connection,
                slug=article.slug,
                author_username=article.author.username,
                new_slug=updated.slug,
                new_title=updated.title,
                new_body=updated.body,
                new_description=updated.description,
            )
            updated.updated_at = result["updated_at"]

        return updated

    async def delete_article(self, *, article: Article) -> None:
        """删除文章"""
        async with self.connection.transaction():
            await queries.delete_article(  # type: ignore
                self.connection,
                slug=article.slug,
                author_username=article.author.username,
            )

    async def filter_articles(
        self, *, tag: Optional[str] = None, author: Optional[str] = None,
        favorited: Optional[str] = None, limit: int = 20, offset: int = 0,
        requested_user: Optional[User] = None,
    ) -> List[Article]:
        """多维度过滤文章列表（使用 pypika 构建安全查询）"""
        param_idx = 0
        query_params: List[Union[str, int]] = []

        # 基础查询：文章 + 作者用户名子查询
        author_subquery = (
            Query.from_(users_table)
            .where(users_table.id == articles_table.author_id)
            .select(users_table.username)
        )

        query = (
            Query.from_(articles_table)
            .select(
                articles_table.id,
                articles_table.slug,
                articles_table.title,
                articles_table.description,
                articles_table.body,
                articles_table.created_at,
                articles_table.updated_at,
                author_subquery.as_("author_username"),
            )
        )

        # 按标签过滤
        if tag:
            param_idx += 1
            query_params.append(tag)
            tag_subquery = (
                Query.from_(tags_table)
                .where(tags_table.tag == AsyncpgParameter(param_idx))
                .select(tags_table.tag)
            )
            query = query.join(articles_to_tags).on(
                (articles_table.id == articles_to_tags.article_id)
                & (articles_to_tags.tag == tag_subquery)
            )

        # 按作者过滤
        if author:
            param_idx += 1
            query_params.append(author)
            author_id_subquery = (
                Query.from_(users_table)
                .where(users_table.username == AsyncpgParameter(param_idx))
                .select(users_table.id)
            )
            query = query.where(articles_table.author_id == author_id_subquery)

        # 按收藏者过滤
        if favorited:
            param_idx += 1
            query_params.append(favorited)
            fav_subquery = (
                Query.from_(users_table)
                .where(users_table.username == AsyncpgParameter(param_idx))
                .select(users_table.id)
            )
            query = query.join(favorites).on(
                (articles_table.id == favorites.article_id)
                & (favorites.user_id == fav_subquery)
            )

        # 分页
        param_idx += 1
        query_params.append(limit)
        query = query.limit(AsyncpgParameter(param_idx))

        param_idx += 1
        query_params.append(offset)
        query = query.offset(AsyncpgParameter(param_idx))

        # 排序
        query = query.orderby(articles_table.created_at, order=Order.desc)

        rows = await self.connection.fetch(query.get_sql(), *query_params)

        return [
            await self._build_article_from_row(row, requested_user=requested_user)
            for row in rows
        ]

    async def get_articles_for_user_feed(
        self, *, user: User, limit: int = 20, offset: int = 0,
    ) -> List[Article]:
        """获取关注用户的文章 Feed"""
        rows = await queries.get_articles_for_feed(  # type: ignore
            self.connection,
            follower_username=user.username,
            limit=limit,
            offset=offset,
        )
        return [
            await self._build_article_from_row(row, requested_user=user)
            for row in rows
        ]

    async def get_tags_for_article_by_slug(self, *, slug: str) -> List[str]:
        """通过 slug 获取文章标签"""
        rows = await queries.get_tags_for_article_by_slug(  # type: ignore
            self.connection, slug=slug,
        )
        return [row["tag"] for row in rows]

    async def get_favorites_count(self, *, slug: str) -> int:
        """获取文章收藏数"""
        result = await queries.get_favorites_count_for_article(  # type: ignore
            self.connection, slug=slug,
        )
        return result["favorites_count"]

    async def is_article_favorited_by_user(self, *, slug: str, user: User) -> bool:
        """检查用户是否收藏了文章"""
        result = await queries.is_article_in_favorites(  # type: ignore
            self.connection, username=user.username, slug=slug,
        )
        return result["favorited"]

    async def add_article_into_favorites(self, *, article: Article, user: User) -> None:
        """收藏文章"""
        await queries.add_article_to_favorites(  # type: ignore
            self.connection, username=user.username, slug=article.slug,
        )

    async def remove_article_from_favorites(self, *, article: Article, user: User) -> None:
        """取消收藏"""
        await queries.remove_article_from_favorites(  # type: ignore
            self.connection, username=user.username, slug=article.slug,
        )

    async def _build_article_from_row(
        self, row, requested_user: Optional[User] = None,
    ) -> Article:
        """从数据库行构建完整的 Article 领域对象"""
        slug = row["slug"]
        author_username = row["author_username"]

        return Article(
            id=row["id"],
            slug=slug,
            title=row["title"],
            description=row["description"],
            body=row["body"],
            author=await self._profiles_repo.get_profile_by_username(
                username=author_username,
                requested_user=requested_user,
            ),
            tags=await self.get_tags_for_article_by_slug(slug=slug),
            favorites_count=await self.get_favorites_count(slug=slug),
            favorited=await self.is_article_favorited_by_user(
                slug=slug, user=requested_user,
            ) if requested_user else False,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )