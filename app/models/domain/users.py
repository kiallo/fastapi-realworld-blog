from typing import Optional
from app.models.domain.rwmodel import RWModel
from app.models.common import IDModelMixin, DateTimeModelMixin


class User(RWModel):
    """用户基础模型 — 不含数据库字段"""
    username: str
    email: str
    bio: str = ""
    image: Optional[str] = None


class UserInDB(IDModelMixin, DateTimeModelMixin, User):
    """
    数据库中的用户 — 继承链：
    IDModelMixin    → id: int
    DateTimeModelMixin → created_at, updated_at
    User            → username, email, bio, image

    额外字段：
    """
    salt: str
    hashed_password: str

    # ===== 业务方法 =====

    def check_password(self, password: str) -> bool:
        """
        验证密码 — 组合 salt + password 后与存储的哈希比对

        注意：这里不直接实现密码验证逻辑，
        实际调用 app.services.security.verify_password()
        """
        from app.services.security import verify_password

        return verify_password(
            salt=self.salt,
            password=password,
            hashed_password=self.hashed_password,
        )

    def change_password(self, new_password: str) -> None:
        """
        修改密码 — 生成新 salt 和新哈希
        """
        from app.services.security import generate_salt, get_password_hash

        self.salt = generate_salt()
        self.hashed_password = get_password_hash(self.salt, new_password)