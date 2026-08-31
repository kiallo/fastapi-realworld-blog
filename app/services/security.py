import bcrypt


def generate_salt() -> str:
    """生成随机 salt"""
    return bcrypt.gensalt().decode()


def get_password_hash(salt: str, password: str) -> str:
    """
    密码 → 哈希

    步骤：salt + password → bcrypt → 哈希字符串
    输出示例：$2b$12$LJ3m4ys3GZfnYMz8qBkpGe...
    """
    return bcrypt.hashpw((salt + password).encode(), salt.encode()).decode()


def verify_password(*, salt: str, password: str, hashed_password: str) -> bool:
    """
    验证密码

    步骤：salt + 用户输入密码 → bcrypt → 与存储的哈希比较
    """
    return bcrypt.checkpw((salt + password).encode(), hashed_password.encode())