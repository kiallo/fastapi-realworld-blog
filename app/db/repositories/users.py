from typing import Optional
import asyncpg
from app.db.repositories.base import BaseRepository
from app.db.queries.queries import queries
from app.db.errors import EntityDoesNotExist
from app.models.domain.users import User, UserInDB
from app.services import security


class UsersRepository(BaseRepository):
    """用户数据访问层"""

    async def get_user_by_email(self, *, email: str) -> UserInDB:
        """根据邮箱查询用户，不存在则抛异常"""
        row = await queries.get_user_by_email(self.connection, email=email)  # type: ignore[attr-defined]
        if row is None:
            raise EntityDoesNotExist(f"邮箱 {email} 的用户不存在")
        return UserInDB(**row)

    async def get_user_by_username(self, *, username: str) -> UserInDB:
        """根据用户名查询用户"""
        row = await queries.get_user_by_username( # type: ignore[attr-defined]
            self.connection, username=username
        )
        if row is None:
            raise EntityDoesNotExist(f"用户名 {username} 不存在")
        return UserInDB(**row)

    async def create_user(self, *, username: str, email: str, password: str) -> UserInDB:
        """创建用户：生成 salt + 哈希 → 写入数据库"""
        salt = security.generate_salt()
        hashed = security.get_password_hash(salt, password)
        
        row = await queries.create_new_user( # type: ignore[attr-defined]
            self.connection,
            username=username,
            email=email,
            salt=salt,
            hashed_password=hashed,
            bio="",
            image=None,
        )
        return UserInDB(**row)

    async def update_user(self, *, user: UserInDB) -> UserInDB:
        """更新用户资料"""
        row = await queries.update_user_by_email(  # type: ignore[attr-defined]
            self.connection,
            username=user.username,
            email=user.email,
            salt=user.salt,
            hashed_password=user.hashed_password,
            bio=user.bio,
            image=user.image,
        )
        # update 没有 RETURNING 所以需要重新查询
        return await self.get_user_by_email(email=user.email)

    