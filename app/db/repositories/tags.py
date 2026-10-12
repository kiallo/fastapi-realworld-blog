from typing import Dict, List, Sequence
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

    async def get_tags_for_articles(
        self, *, slugs: Sequence[str],
    ) -> Dict[str, List[str]]:
        """
        ★ 批量获取多篇文章的标签 —— 一条 SQL 解决，替代 N 次单篇查询

        返回 {slug: [tag, ...]}；没有标签的文章也会以空列表出现。
        """
        if not slugs:
            return {}

        slug_list = list(slugs)
        rows = await queries.get_tags_for_articles_by_slugs(  # type: ignore
            self.connection, slugs=slug_list,
        )

        tags_by_slug: Dict[str, List[str]] = {slug: [] for slug in slug_list}
        for row in rows:
            tags_by_slug.setdefault(row["slug"], []).append(row["tag"])
        return tags_by_slug

    async def link_article_with_tags(self, *, article_id: int, tags: List[str]) -> None:
        """关联文章与标签"""
        for tag in tags:
            await queries.link_article_tag( # type: ignore
                self.connection, article_id=article_id, tag=tag
            )

    