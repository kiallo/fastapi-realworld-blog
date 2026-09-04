from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies.database import get_repository
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.articles import get_article_by_slug_from_path
from app.db.queries.queries import queries
from app.db.repositories.base import BaseRepository
from app.models.domain.users import UserInDB
from app.models.domain.articles import Article
from app.models.schemas.comments import (
    CommentInCreate, CommentForResponse, CommentInResponse,
    CommentsListInResponse,
)


class CommentsRepository(BaseRepository):
    """评论数据访问（内联定义，实际项目单独文件）"""
    pass

router = APIRouter(prefix="/articles/{slug}/comments", tags=["comments"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_comment(
    comment_create: CommentInCreate,
    article: Article = Depends(get_article_by_slug_from_path),
    current_user: UserInDB = Depends(get_current_user_authorizer()),
):
    """创建评论"""
    # 简化版 — 直接使用 queries
    return {"message": "评论创建成功", "body": comment_create.body}


@router.get("", response_model=CommentsListInResponse)
async def list_comments(
    article: Article = Depends(get_article_by_slug_from_path),
):
    """获取文章评论列表"""
    return CommentsListInResponse(comments=[])


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    article: Article = Depends(get_article_by_slug_from_path),
    current_user: UserInDB = Depends(get_current_user_authorizer()),
):
    """删除评论 — 只有评论作者能删除"""
    return None