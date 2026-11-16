import datetime

from app.models.common import DateTimeModelMixin, IDModelMixin
from app.models.domain.rwmodel import RWModel


class Comment(IDModelMixin, DateTimeModelMixin, RWModel):
    """评论 Domain 模型"""

    body: str
    author: "Profile"  # 评论者资料


# 解决循环引用
from app.models.domain.profiles import Profile  # noqa: E402

Comment.model_rebuild()
