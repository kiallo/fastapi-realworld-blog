from fastapi import APIRouter, Depends
from app.api.dependencies.database import get_repository
from app.db.repositories.tags import TagsRepository


router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
async def get_all_tags(
    tags_repo: TagsRepository = Depends(get_repository(TagsRepository)),
):
    """获取所有标签"""
    tags = await tags_repo.get_all_tags()
    return {"tags": tags}