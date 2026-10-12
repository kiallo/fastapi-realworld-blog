from typing import Dict, Optional, Sequence, Set, Union

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

    async def get_profiles_by_usernames(
        self, *, usernames: Sequence[str],
        requested_user: Optional[UserLike] = None,
    ) -> Dict[str, Profile]:
        """
        ★ 批量获取多个用户的公开资料 —— 最多两条 SQL，替代 N 次单用户查询

        1 条查所有用户的基础资料；
        登录时再加 1 条，查出"关注了其中哪几个"。

        返回 {username: Profile}；查不到的用户不会出现在结果里。
        """
        if not usernames:
            return {}

        username_list = list(dict.fromkeys(usernames))  # 去重，保持顺序
        rows = await queries.get_users_by_usernames(  # type: ignore
            self.connection, usernames=username_list,
        )

        following: Set[str] = set()
        if requested_user:
            following_rows = await queries.get_following_usernames_for_user(  # type: ignore
                self.connection,
                follower_username=requested_user.username,
                usernames=username_list,
            )
            following = {row["username"] for row in following_rows}

        return {
            row["username"]: Profile(
                username=row["username"],
                bio=row.get("bio") or "",
                image=row.get("image"),
                following=row["username"] in following,
            )
            for row in rows
        }

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