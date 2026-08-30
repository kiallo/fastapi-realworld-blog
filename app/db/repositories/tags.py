from typing import List
import asyncpg
from app.db.repositories.base import BaseRepository
from app.db.queries.queries import queries


class TagsRepository(BaseRepository):
    """标签数据访问"""

    async def get_all_tags(self) -> List[str]:
        rows = await queries.get_all_tags(self.connection)  # type: ignore
        return [r["tag"] for r in rows]

    async def create_tags_that_dont_exist(self, *, tags: List[str]) -> None:
        """批量插入不存在的标签"""
        for tag in tags:
            await queries.create_tag(self.connection, tag=tag) # type: ignore

    async def get_tags_for_article(self, *, article_id: int) -> List[str]:
        rows = await queries.get_tags_for_article( # type: ignore
            self.connection, article_id=article_id
        )
        return [r["tag"] for r in rows]

    async def link_article_with_tags(self, *, article_id: int, tags: List[str]) -> None:
        """关联文章与标签"""
        for tag in tags:
            await queries.link_article_tag( # type: ignore
                self.connection, article_id=article_id, tag=tag
            )

    