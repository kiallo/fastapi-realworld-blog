from fastapi import APIRouter

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.get("/{user_id}")
async def get_user(user_id: int):
    """获取单个用户"""
    return {"user_id": user_id}

