import bcrypt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_salt() -> str:
    """生成随机 salt"""
    return bcrypt.gensalt().decode()


def get_password_hash(salt: str, password: str) -> str:
    """salt + password → bcrypt 哈希"""
    return pwd_context.hash(salt + password)


def verify_password(*, salt: str, password: str, hashed_password: str) -> bool:
    """验证密码：salt + password 的哈希是否等于存储的哈希"""
    return pwd_context.verify(salt + password, hashed_password)