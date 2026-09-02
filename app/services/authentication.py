from app.db.repositories.users import UsersRepository
from app.db.errors import EntityDoesNotExist


async def check_username_is_taken(
    users_repo: UsersRepository, username: str
) -> bool:
    """检查用户名是否已被占用"""
    try:
        await users_repo.get_user_by_username(username=username)
        return True
    except EntityDoesNotExist:
        return False


async def check_email_is_taken(
    users_repo: UsersRepository, email: str
) -> bool:
    """检查邮箱是否已被注册"""
    try:
        await users_repo.get_user_by_email(email=email)
        return True
    except EntityDoesNotExist:
        return False