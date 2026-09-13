"""
会话管理演示接口

用于测试和演示 Redis 会话管理功能
"""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.dependencies import get_redis
from app.api.dependencies.authentication import get_current_user_authorizer
from app.models.domain.users import UserInDB
from app.services.token_storage import TokenStorage
from app.core.dependencies import get_token_storage

router = APIRouter(prefix="/session", tags=["session-demo"])


@router.get("/info")
async def get_my_session(
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    token_storage: TokenStorage = Depends(get_token_storage),
):
    """
    获取当前用户的会话信息

    返回：登录时间、设备信息、Token 剩余有效期
    """
    session_info = await token_storage.get_session_info(current_user.username)
    if session_info:
        return {
            "username": current_user.username,
            "session": session_info,
        }
    return {
        "username": current_user.username,
        "session": None,
        "message": "无活跃会话",
    }


@router.get("/online")
async def get_online_users(
    token_storage: TokenStorage = Depends(get_token_storage),
):
    """
    获取在线用户列表

    从 Redis 的 online:users 集合中读取
    """
    users = await token_storage.get_online_users()
    count = await token_storage.get_online_count()

    return {
        "online_users": users,
        "count": count,
    }


@router.post("/force-logout/{username}")
async def force_logout_user(
    username: str,
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    token_storage: TokenStorage = Depends(get_token_storage),
):
    """
    强制指定用户下线（管理员功能演示）

    注意：这里简化处理，实际项目应加管理员权限校验
    """
    if current_user.username != username:
        # 简化：只允许自己强制自己下线（演示用）
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能管理自己的会话",
        )

    result = await token_storage.force_logout(username)
    if result:
        return {"message": f"用户 {username} 已被强制下线"}
    return {"message": f"用户 {username} 没有活跃会话"}


router.get("/validate")
async def validate_session(
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    token_storage: TokenStorage = Depends(get_token_storage),
):
    """验证当前会话是否有效"""
    session_info = await token_storage.get_session_info(current_user.username)

    return {
        "valid": True,
        "username": current_user.username,
        "ttl_seconds": session_info.get("ttl_seconds") if session_info else None,
    }