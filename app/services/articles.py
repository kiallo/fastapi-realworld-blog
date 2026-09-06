from slugify import slugify

from app.db.errors import EntityDoesNotExist
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.articles import Article
from app.models.domain.users import User


async def check_article_exists(articles_repo: ArticlesRepository, slug: str) -> bool:
    """检查文章是否已存在"""
    try:
        await articles_repo.get_article_by_slug(slug=slug)
    except EntityDoesNotExist:
        return False
    return True


def get_slug_for_article(title: str) -> str:
    """根据标题生成 URL slug"""
    return slugify(title)


def check_user_can_modify_article(article: Article, user: User) -> bool:
    """检查用户是否有权限修改文章 — 只有作者可以"""
    return article.author.username == user.username
