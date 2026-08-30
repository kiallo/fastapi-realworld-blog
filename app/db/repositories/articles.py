from typing import List, Optional
import asyncpg
from slugify import slugify
from app.db.repositories.base import BaseRepository
from app.db.repositories.tags import TagsRepository
from app.db.queries.queries import queries
from app.db.errors import EntityDoesNotExist
from app.models.domain.articles import Article
from app.models.domain.users import UserInDB


DEFAULT_ARTICLES_LIMIT = 20
DEFAULT_ARTICLES_OFFSET = 0


class ArticlesRepository(BaseRepository):
    async def create_article(
        self, *, slug: str, title: str, description: str,
        body: str, author: UserInDB, tags: List[str],
    ) -> Article:
        """创建文章 + 标签关联 — 整个操作在事务中完成"""
        async with self.connection.transaction():
            # 步骤 1：创建文章
            row = await queries.create_article( # type: ignore
                self.connection,
                slug=slug,
                title=title,
                description=description,
                body=body,
                author_id=author.id,
            )

            # 步骤 2：创建不存在的标签
            tags_repo = TagsRepository(self.connection)
            await tags_repo.create_tags_that_dont_exist(tags=tags)

            # 步骤 3：关联标签
            await tags_repo.link_article_with_tags(
                article_id=row["id"], tags=tags
            )

        # 任何步骤失败 → 自动回滚 → 数据库没有任何变化
        return await self._build_article_response(row)

    async def get_article_by_slug(self, *, slug: str) -> Article:
        row = await queries.get_article_by_slug(self.connection, slug=slug) # type: ignore
        if row is None:
            raise EntityDoesNotExist(f"文章 {slug} 不存在")
        return await self._build_article_response(row)

    async def _build_article_response(self, row: dict) -> Article:
        """组装完整的 Article 对象（含标签、作者信息）"""
        # 获取标签
        tags_repo = TagsRepository(self.connection)
        tag_list = await tags_repo.get_tags_for_article(article_id=row["id"])

        # 获取作者信息
        from app.db.repositories.users import UsersRepository
        # 这里通过查询构造 Profile，实际项目中会专门写这个方法
        users_repo = UsersRepository(self.connection)
        # 简化处理：直接返回文章数据
        # 完整的作者 profile 在第 27 课实现

        return Article(
            id=row["id"],
            slug=row["slug"],
            title=row["title"],
            description=row["description"],
            body=row["body"],
            tags=tag_list,
            author={"username": ""},  # 会在路由层补充 # type: ignore
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )