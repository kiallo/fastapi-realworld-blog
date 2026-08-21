from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.schemas.rwschema import RWSchema

# 默认分页参数
DEFAULT_ARTICLES_LIMIT = 20
DEFAULT_ARTICLES_OFFSET = 0


# ===== 请求 Schema =====

class ArticleInCreate(RWSchema):
    """创建文章请求"""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    tag_list: List[str] = Field([], alias="tagList")


class ArticleInUpdate(RWSchema):
    """更新文章请求 — 所有字段可选（部分更新）"""
    title: Optional[str] = None
    description: Optional[str] = None
    body: Optional[str] = None


# ===== 响应 Schema =====

class ArticleForResponse(RWSchema):
    """单篇文章响应"""
    slug: str
    title: str
    description: str
    body: str
    tag_list: List[str] = Field([], alias="tagList")
    created_at: str
    updated_at: str
    favorited: bool = False
    favorites_count: int = Field(0, alias="favoritesCount")
    author: dict = {}  # Profile 信息


class ArticleInResponse(RWSchema):
    """{ "article": {...} } 包装格式"""
    article: ArticleForResponse


class ArticlesListInResponse(RWSchema):
    """文章列表响应"""
    articles: List[ArticleForResponse]
    articles_count: int = Field(..., alias="articlesCount")


# ===== 非 Schema 的路由参数聚合模型 =====


class ArticlesFilters(BaseModel):
    """文章列表的查询参数聚合（不需要 RWModel 的后处理）"""
    tag: Optional[str] = None
    author: Optional[str] = None
    favorited: Optional[str] = None
    limit: int = DEFAULT_ARTICLES_LIMIT
    offset: int = DEFAULT_ARTICLES_OFFSET