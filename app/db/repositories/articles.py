from typing import Dict, List, Optional, Sequence, Set, Union

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
                author_id=author.id,                         # type: ignore
            )

            # 步骤 2：创建不存在的标签
            if tags:
                await self._tags_repo.create_tags_that_dont_exist(tags=tags) # type: ignore

                # 步骤 3：关联标签
                await self._tags_repo.link_article_with_tags(
                    article_id=row["id"], tags=list(tags)
                )

        # 任何步骤失败 → 自动回滚 → 数据库没有任何变化
        # ★ 第 59 行：不再用 RETURNING 那行（它没有 author_username），改成事务外重新查
        return await self.get_article_by_slug(slug=slug, requested_user=author)

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
            new_updated_at = await queries.update_article(  # type: ignore
                self.connection,
                slug=article.slug,
                author_username=article.author.username,
                new_slug=updated.slug,
                new_title=updated.title,
                new_body=updated.body,
                new_description=updated.description,
            )
            updated.updated_at = new_updated_at # type: ignore

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
            .where(users_table.id == articles_table.author_id) # type: ignore
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
                .where(tags_table.tag == AsyncpgParameter(param_idx)) # type: ignore
                .select(tags_table.tag)
            )
            query = query.join(articles_to_tags).on(
                (articles_table.id == articles_to_tags.article_id)
                & (articles_to_tags.tag == tag_subquery) # type: ignore
            )

        # 按作者过滤
        if author:
            param_idx += 1
            query_params.append(author)
            author_id_subquery = (
                Query.from_(users_table)
                .where(users_table.username == AsyncpgParameter(param_idx)) # type: ignore
                .select(users_table.id)
            )
            query = query.where(articles_table.author_id == author_id_subquery) # type: ignore

        # 按收藏者过滤
        if favorited:
            param_idx += 1
            query_params.append(favorited)
            fav_subquery = (
                Query.from_(users_table)
                .where(users_table.username == AsyncpgParameter(param_idx)) # type: ignore
                .select(users_table.id)
            )
            query = query.join(favorites).on(
                (articles_table.id == favorites.article_id)
                & (favorites.user_id == fav_subquery) # type: ignore
            )

        # 分页
        param_idx += 1
        query_params.append(limit)
        query = query.limit(AsyncpgParameter(param_idx)) # type: ignore

        param_idx += 1
        query_params.append(offset)
        query = query.offset(AsyncpgParameter(param_idx)) # type: ignore

        # 排序
        query = query.orderby(articles_table.created_at, order=Order.desc)

        rows = await self.connection.fetch(query.get_sql(), *query_params)

        # ★ 批量构建：整页文章只用固定几条 SQL，不再是"每篇 3~5 条"
        return await self._build_articles_from_rows(
            rows, requested_user=requested_user,
        )

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
        return await self._build_articles_from_rows(rows, requested_user=user)

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
        """从数据库行构建完整的 Article 领域对象（单篇）

        ★ 内部走批量实现，只是把"一行"当成"一批只有一行" ——
        这样单篇和列表共用同一段逻辑，不会出现"改了列表忘了改详情"的分叉。
        """
        articles = await self._build_articles_from_rows(
            [row], requested_user=requested_user,
        )
        return articles[0]

    async def _build_articles_from_rows(
        self, rows, requested_user: Optional[User] = None,
    ) -> List[Article]:
        """★ 批量构建 Article 领域对象 —— 消灭 N+1

        改造前：每篇文章都要单独查 作者资料 / 标签 / 收藏数 /（登录时）是否收藏，
                20 篇的列表页要发 61（匿名）~ 101（登录）条 SQL。

        改造后：先把所有文章需要的 id/username 收集起来，每类数据只查一次：
                1  条主查询（列表本身）
              + 1  条查所有作者资料（登录时 +1 条查关注状态）
              + 1  条查所有标签
              + 1  条查所有收藏数
              + 1  条查"我收藏了哪几篇"（仅登录）
              = 4 条（匿名）/ 6 条（登录），**与返回多少篇文章无关**。
        """
        if not rows:
            return []

        # 去重：20 篇文章可能来自同几个作者，作者资料没必要重复查
        slugs = list(dict.fromkeys(row["slug"] for row in rows))
        author_usernames = list(
            dict.fromkeys(row["author_username"] for row in rows)
        )

        tags_by_slug = await self._tags_repo.get_tags_for_articles(slugs=slugs)
        favorites_counts = await self._get_favorites_counts(slugs=slugs)

        favorited_slugs: Set[str] = set()
        if requested_user:
            favorited_slugs = await self._get_favorited_slugs(
                slugs=slugs, user=requested_user,
            )

        profiles_by_username = await self._profiles_repo.get_profiles_by_usernames(
            usernames=author_usernames, requested_user=requested_user,
        )

        articles: List[Article] = []
        for row in rows:
            author = profiles_by_username.get(row["author_username"])
            if author is None:
                # 外键保证不该发生，但真发生了要报得清楚，而不是 KeyError
                raise EntityDoesNotExist(f"用户 {row['author_username']} 不存在")

            articles.append(
                Article(
                    id=row["id"],
                    slug=row["slug"],
                    title=row["title"],
                    description=row["description"],
                    body=row["body"],
                    author=author,
                    tags=tags_by_slug.get(row["slug"], []),
                    favorites_count=favorites_counts.get(row["slug"], 0),
                    favorited=row["slug"] in favorited_slugs,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return articles

    async def _get_favorites_counts(self, *, slugs: Sequence[str]) -> Dict[str, int]:
        """★ 批量：一次查出多篇文章的收藏数，返回 {slug: count}"""
        if not slugs:
            return {}
        rows = await queries.get_favorites_count_for_articles(  # type: ignore
            self.connection, slugs=list(slugs),
        )
        return {row["slug"]: row["favorites_count"] for row in rows}

    async def _get_favorited_slugs(
        self, *, slugs: Sequence[str], user: User,
    ) -> Set[str]:
        """★ 批量：一次查出"该用户收藏了这批文章里的哪几篇" """
        if not slugs:
            return set()
        rows = await queries.get_favorited_slugs_for_user(  # type: ignore
            self.connection, username=user.username, slugs=list(slugs),
        )
        return {row["slug"] for row in rows}