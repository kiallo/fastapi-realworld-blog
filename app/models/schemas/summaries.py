from typing import Literal

from pydantic import Field

from app.models.schemas.rwschema import RWSchema

class ArticleSummaryContent(RWSchema):
    """LLM 返回的摘要内容（结构化输出）"""
    summary: str = Field(..., min_length=10, max_length=300)
    keywords: list[str] = Field(..., min_length=2, max_length=5)
    difficulty: Literal["beginner", "intermediate", "advanced"]


class ArticleSummaryInResponse(RWSchema):
    """接口响应：{ "summary": {...}, "model": "...", "cached": false }"""
    summary: ArticleSummaryContent
    model: str
    cached: bool = False