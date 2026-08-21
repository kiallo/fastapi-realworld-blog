from typing import List, Optional
from pydantic import Field
from app.models.schemas.rwschema import RWSchema


class CommentInCreate(RWSchema):
    """创建评论请求"""
    body: str = Field(..., min_length=1, max_length=5000)


class CommentForResponse(RWSchema):
    """评论响应"""
    id: int
    body: str
    created_at: str
    updated_at: str
    author: dict = {}


class CommentInResponse(RWSchema):
    """{ "comment": {...} } 包装格式"""
    comment: CommentForResponse


class CommentsListInResponse(RWSchema):
    """评论列表响应"""
    comments: List[CommentForResponse]