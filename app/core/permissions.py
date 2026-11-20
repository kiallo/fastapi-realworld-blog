"""角色与权限的唯一映射表。

设计取舍（详见第 28 课 2.1）：
  - 角色存数据库（users.role 一列），因为它是数据；
  - 权限写在这里（代码里），因为权限点就是端点，端点在代码里。

这张表只描述"超出普通用户的特权"。读者/作者能做的事是"登录即可"，
不需要在这里声明，否则每加一个接口都要回来补一行。
"""

from enum import Enum

from app.models.domain.users import Role


class Permission(str, Enum):
    """权限点 — 命名规范：对象:动作:范围"""

    ARTICLE_UPDATE_ANY = "article:update:any"
    ARTICLE_DELETE_ANY = "article:delete:any"
    COMMENT_DELETE_ANY = "comment:delete:any"
    USER_MANAGE = "user:manage"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.READER: frozenset(),
    Role.AUTHOR: frozenset(),
    Role.ADMIN: frozenset(
        {
            Permission.ARTICLE_UPDATE_ANY,
            Permission.ARTICLE_DELETE_ANY,
            Permission.COMMENT_DELETE_ANY,
            Permission.USER_MANAGE,
        }
    ),
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    """唯一的判定入口 — 业务代码不要自己 if role == 'admin'"""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
