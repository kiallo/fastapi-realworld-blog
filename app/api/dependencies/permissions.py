"""权限依赖 — 让"要求某权限"变成一行 Depends。"""

from typing import Awaitable, Callable

from fastapi import Depends, HTTPException
from starlette import status

from app.api.dependencies.authentication import get_current_user_authorizer
from app.core.metrics import AUTHZ_DENIED_TOTAL
from app.core.permissions import Permission, role_has_permission
from app.models.domain.users import UserInDB


def require_permission(permission: Permission) -> Callable[..., Awaitable[None]]:
    """返回一个依赖：当前用户没有该权限就 403，并记一次拒绝计数。

    用法：dependencies=[Depends(require_permission(Permission.USER_MANAGE))]
    """

    async def _checker(
        current_user: UserInDB = Depends(get_current_user_authorizer()),
    ) -> None:
        if role_has_permission(current_user.role, permission):
            return

        AUTHZ_DENIED_TOTAL.labels(
            permission=permission.value,
            role=current_user.role.value,
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"缺少权限：{permission.value}",
        )

    return _checker