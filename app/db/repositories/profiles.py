from typing import Optional, Union

from asyncpg import Connection

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.repositories.base import BaseRepository
from app.models.domain.profiles import Profile
from app.models.domain.users import User

UserLike = Union[User, Profile]


class ProfilesRepository(BaseRepository):

    async def get_profile_by_username(
        self, *, username: str, current_user_id: Optional[int] = None,
        requested_user: Optional[UserLike] = None,
    ) -> Profile:
        """获取用户公开资料 — 含关注状态"""
        row = await queries.get_user_by_username(  # type: ignore
            self.connection, username=username
        )
        if row is None:
            raise EntityDoesNotExist(f"用户 {username} 不存在")

        following = False
        if requested_user:
            result = await queries.is_user_following_for_another(  # type: ignore
                self.connection,
                follower_username=requested_user.username,
                following_username=username,
            )
            following = result["is_following"] if result else False
        elif current_user_id:
            result = await queries.is_user_following(  # type: ignore
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

    async def add_user_into_followers(
        self, *, target_user: UserLike, requested_user: UserLike,
    ) -> None:
        """关注用户"""
        async with self.connection.transaction():
            await queries.subscribe_user_to_another(  # type: ignore
                self.connection,
                follower_username=requested_user.username,
                following_username=target_user.username,
            )

    async def remove_user_from_followers(
        self, *, target_user: UserLike, requested_user: UserLike,
    ) -> None:
        """取消关注"""
        async with self.connection.transaction():
            await queries.unsubscribe_user_from_another(  # type: ignore
                self.connection,
                follower_username=requested_user.username,
                following_username=target_user.username,
            )