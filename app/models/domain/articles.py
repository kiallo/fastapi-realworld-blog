from typing import Optional, List
import datetime
from app.models.domain.rwmodel import RWModel
from app.models.common import IDModelMixin, DateTimeModelMixin


class Article(IDModelMixin, DateTimeModelMixin, RWModel):
    """文章 Domain 模型"""
    slug: str
    title: str
    description: str
    body: str
    tags: List[str] = []
    author: "Profile"  # 前向引用，定义在 profiles.py 中
    favorited: bool = False
    favorites_count: int = 0


# 解决循环引用
from app.models.domain.profiles import Profile  # noqa: E402
Article.model_rebuild()