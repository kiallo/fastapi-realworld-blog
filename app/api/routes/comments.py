from typing import Optional

from fastapi import APIRouter, Body, Depends, Response
from starlette import status

from app.api.dependencies.articles import get_article_by_slug_from_path
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.comments import (
    check_comment_modification_permissions,
    get_comment_by_id_from_path,
)
from app.api.dependencies.database import get_repository
from app.db.repositories.comments import CommentsRepository
from app.models.domain.articles import Article
from app.models.domain.comments import Comment
from app.models.domain.users import User
from app.models.schemas.comments import (
    CommentForResponse,
    CommentInCreate,
    CommentInResponse,
    CommentsListInResponse,
)

router = APIRouter()


def _comment_to_response(comment: Comment) -> CommentForResponse:
    """Comment 领域对象 → 响应 Schema"""
    from app.models.schemas.profiles import ProfileForResponse

    return CommentForResponse(
        id=comment.id,
        body=comment.body,
        created_at=str(comment.created_at),
        updated_at=str(comment.updated_at),
        author=ProfileForResponse(
            username=comment.author.username,
            bio=comment.author.bio,
            image=comment.author.image,
            following=comment.author.following,
        ),
    )


@router.get(
    "",
    response_model=CommentsListInResponse,
    name="comments:get-comments-for-article",
)
async def list_comments_for_article(
    article: Article = Depends(get_article_by_slug_from_path),
    user: Optional[User] = Depends(get_current_user_authorizer(required=False)),
    comments_repo: CommentsRepository = Depends(get_repository(CommentsRepository)),
) -> CommentsListInResponse:
    """获取文章的评论列表"""
    comments = await comments_repo.get_comments_for_article(
        article=article,
        user=user,
    )
    return CommentsListInResponse(
        comments=[_comment_to_response(c) for c in comments]
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CommentInResponse,
    name="comments:create-comment-for-article",
)
async def create_comment_for_article(
    comment_create: CommentInCreate = Body(..., embed=True, alias="comment"),
    article: Article = Depends(get_article_by_slug_from_path),
    user: User = Depends(get_current_user_authorizer()),
    comments_repo: CommentsRepository = Depends(get_repository(CommentsRepository)),
) -> CommentInResponse:
    """为文章创建评论"""
    comment = await comments_repo.create_comment_for_article(
        body=comment_create.body,
        article=article,
        user=user,
    )
    return CommentInResponse(comment=_comment_to_response(comment))


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="comments:delete-comment-from-article",
    dependencies=[Depends(check_comment_modification_permissions)],
    response_class=Response,
)
async def delete_comment_from_article(
    comment: Comment = Depends(get_comment_by_id_from_path),
    comments_repo: CommentsRepository = Depends(get_repository(CommentsRepository)),
) -> None:
    """删除评论 — 只有评论作者可以删除"""
    await comments_repo.delete_comment(comment=comment)
