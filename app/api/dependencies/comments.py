from typing import Optional

from fastapi import Depends, HTTPException, Path
from starlette import status

from app.api.dependencies import articles, authentication, database
from app.db.errors import EntityDoesNotExist
from app.db.repositories.comments import CommentsRepository
from app.models.domain.articles import Article
from app.models.domain.comments import Comment
from app.models.domain.users import User, UserInDB
from app.resources import strings
from app.services.comments import check_user_can_modify_comment
from app.core.metrics import AUTHZ_DENIED_TOTAL
from app.core.permissions import Permission, role_has_permission


async def get_comment_by_id_from_path(
    comment_id: int = Path(..., ge=1),
    article: Article = Depends(articles.get_article_by_slug_from_path),
    user: Optional[User] = Depends(
        authentication.get_current_user_authorizer(required=False),
    ),
    comments_repo: CommentsRepository = Depends(
        database.get_repository(CommentsRepository),
    ),
) -> Comment:
    """从 URL 路径中获取评论 — 自动校验文章是否存在"""
    try:
        return await comments_repo.get_comment_by_id(
            comment_id=comment_id,
            article=article,
            user=user,
        )
    except EntityDoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=strings.COMMENT_DOES_NOT_EXIST,
        )


def check_comment_modification_permissions(
    comment: Comment = Depends(get_comment_by_id_from_path),
    user: UserInDB = Depends(authentication.get_current_user_authorizer()),
) -> None:
    """评论作者本人，或持有 comment:delete:any 的角色（管理员）"""
    if check_user_can_modify_comment(comment, user):
        return

    if role_has_permission(user.role, Permission.COMMENT_DELETE_ANY):
        return

    AUTHZ_DENIED_TOTAL.labels(
        permission=Permission.COMMENT_DELETE_ANY.value,
        role=user.role.value,
    ).inc()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=strings.USER_IS_NOT_AUTHOR_OF_ARTICLE,
    )
