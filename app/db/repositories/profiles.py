from typing import Optional
import asyncpg
from app.db.repositories.base import BaseRepository
from app.db.queries.queries import queries
from app.db.errors import EntityDoesNotExist
from app.models.domain.profiles import Profile


class ProfilesRepository(BaseRepository):

    async def get_profile_by_username(
        self, *, username: str, current_user_id: Optional[int] = None,
    ) -> Profile:
        """获取用户公开资料 — 含关注状态"""
        row = await queries.get_user_by_username( # type: ignore
            self.connection, username=username
        )
        if row is None:
            raise EntityDoesNotExist(f"用户 {username} 不存在")

        following = False
        if current_user_id:
            result = await queries.is_user_following( # type: ignore
                self.connection,
                follower_id=current_user_id,
                following_id=row["id"],
            )
            following = result["following"] if result else False

        return Profile(
            username=row["username"],
            bio=row.get("bio", ""),
            image=row.get("image"),
            following=following,
        )