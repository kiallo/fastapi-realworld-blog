from app.models.domain.comments import Comment
from app.models.domain.users import User


def check_user_can_modify_comment(comment: Comment, user: User) -> bool:
    """检查用户是否有权限修改/删除评论 — 只有评论作者可以"""
    return comment.author.username == user.username
