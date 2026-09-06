from typing import List, Optional

from asyncpg import Connection, Record

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.repositories.base import BaseRepository
from app.db.repositories.profiles import ProfilesRepository
from app.models.domain.articles import Article
from app.models.domain.comments import Comment
from app.models.domain.users import User


class CommentsRepository(BaseRepository):
    """评论数据访问层"""

    def __init__(self, conn: Connection) -> None:
        super().__init__(conn)
        self._profiles_repo = ProfilesRepository(conn)

    async def get_comment_by_id(
        self,
        *,
        comment_id: int,
        article: Article,
        user: Optional[User] = None,
    ) -> Comment:
        """通过评论 ID + 文章获取单条评论"""
        comment_row = await queries.get_comment_by_id_and_slug(  # type: ignore
            self.connection,
            comment_id=comment_id,
            article_slug=article.slug,
        )
        if comment_row:
            return await self._build_comment(
                comment_row=comment_row,
                author_username=comment_row["author_username"],
                requested_user=user,
            )

        raise EntityDoesNotExist(
            f"评论 {comment_id} 不存在"
        )

    async def get_comments_for_article(
        self,
        *,
        article: Article,
        user: Optional[User] = None,
    ) -> List[Comment]:
        """获取文章的所有评论"""
        comments_rows = await queries.get_comments_for_article_by_slug(  # type: ignore
            self.connection,
            slug=article.slug,
        )
        return [
            await self._build_comment(
                comment_row=comment_row,
                author_username=comment_row["author_username"],
                requested_user=user,
            )
            for comment_row in comments_rows
        ]

    async def create_comment_for_article(
        self,
        *,
        body: str,
        article: Article,
        user: User,
    ) -> Comment:
        """为文章创建评论"""
        comment_row = await queries.create_new_comment(  # type: ignore
            self.connection,
            body=body,
            article_slug=article.slug,
            author_username=user.username,
        )
        return await self._build_comment(
            comment_row=comment_row,
            author_username=comment_row["author_username"],
            requested_user=user,
        )

    async def delete_comment(self, *, comment: Comment) -> None:
        """删除评论（只能删除自己的）"""
        await queries.delete_comment_by_slug(  # type: ignore
            self.connection,
            comment_id=comment.id,
            author_username=comment.author.username,
        )

    async def _build_comment(
        self,
        *,
        comment_row: Record,
        author_username: str,
        requested_user: Optional[User],
    ) -> Comment:
        """从数据库记录构建 Comment 领域对象"""
        return Comment(
            id=comment_row["id"],
            body=comment_row["body"],
            author=await self._profiles_repo.get_profile_by_username(
                username=author_username,
                requested_user=requested_user,
            ),
            created_at=comment_row["created_at"],
            updated_at=comment_row["updated_at"],
        )
