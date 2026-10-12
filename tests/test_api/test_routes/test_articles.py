"""文章 Repository 测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.db.repositories.articles import ArticlesRepository
from app.db.errors import EntityDoesNotExist
from app.models.domain.articles import Article
from app.models.domain.profiles import Profile


@pytest.fixture
def mock_conn():
    return MagicMock()


@pytest.fixture
def mock_article():
    return Article(
        id=1,
        slug="test-article",
        title="Test Article",
        description="A test article",
        body="Article body content",
        author=Profile(username="author", bio="author bio", image=None, following=False),
        tags=["python", "fastapi"],
        favorited=False,
        favorites_count=0,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def mock_article_row():
    return {
        "id": 1,
        "slug": "test-article",
        "title": "Test Article",
        "description": "A test article",
        "body": "Article body content",
        "author_username": "author",
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1),
    }


@pytest.mark.asyncio
async def test_get_article_by_slug(mock_conn, mock_article_row):
    """get_article_by_slug — 获取文章"""
    with patch("app.db.repositories.articles.queries") as mock_queries, \
         patch("app.db.repositories.articles.ProfilesRepository") as MockProfilesRepo, \
         patch("app.db.repositories.articles.TagsRepository") as MockTagsRepo:
        mock_queries.get_article_by_slug = AsyncMock(return_value=mock_article_row)
        # ★ 改造后走的是"批量"方法：一次查一批文章
        mock_queries.get_favorites_count_for_articles = AsyncMock(
            return_value=[{"slug": "test-article", "favorites_count": 0}]
        )
        MockProfilesRepo.return_value.get_profiles_by_usernames = AsyncMock(
            return_value={
                "author": Profile(username="author", bio="", image=None, following=False)
            }
        )
        MockTagsRepo.return_value.get_tags_for_articles = AsyncMock(
            return_value={"test-article": ["python", "fastapi"]}
        )

        repo = ArticlesRepository(mock_conn)
        article = await repo.get_article_by_slug(slug="test-article")

    assert article.slug == "test-article"
    assert article.title == "Test Article"
    assert article.author.username == "author"
    assert article.tags == ["python", "fastapi"]


@pytest.mark.asyncio
async def test_get_article_not_found(mock_conn):
    """get_article_by_slug — 文章不存在"""
    with patch("app.db.repositories.articles.queries") as mock_queries:
        mock_queries.get_article_by_slug = AsyncMock(return_value=None)

        repo = ArticlesRepository(mock_conn)
        with pytest.raises(EntityDoesNotExist):
            await repo.get_article_by_slug(slug="nonexistent")


@pytest.mark.asyncio
async def test_create_article(mock_conn, mock_article_row):
    """create_article — 创建文章"""
    from app.models.domain.users import UserInDB
    from app.models.domain.profiles import Profile as ProfileModel

    mock_user = UserInDB(
        id=1,
        username="author",
        email="author@test.com",
        salt="salt",
        hashed_password="hashed",
        bio="",
        image=None,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )

    with patch("app.db.repositories.articles.queries") as mock_queries, \
         patch("app.db.repositories.articles.ProfilesRepository") as MockProfilesRepo, \
         patch("app.db.repositories.articles.TagsRepository") as MockTagsRepo:
        mock_queries.create_article = AsyncMock(return_value=mock_article_row)
        # create_article 最后会重新查一遍这篇文章，这里也要 mock（原来漏了）
        mock_queries.get_article_by_slug = AsyncMock(return_value=mock_article_row)
        # ★ 改造后走的是"批量"方法：一次查一批文章
        mock_queries.get_favorites_count_for_articles = AsyncMock(
            return_value=[{"slug": "test-article", "favorites_count": 0}]
        )
        # 创建时带的是登录用户，所以还会多查一次"我收藏了哪几篇"
        mock_queries.get_favorited_slugs_for_user = AsyncMock(return_value=[])
        MockProfilesRepo.return_value.get_profiles_by_usernames = AsyncMock(
            return_value={
                "author": ProfileModel(
                    username="author", bio="", image=None, following=False
                )
            }
        )
        MockTagsRepo.return_value.get_tags_for_articles = AsyncMock(
            return_value={"test-article": ["python"]}
        )
        MockTagsRepo.return_value.create_tags_that_dont_exist = AsyncMock()
        MockTagsRepo.return_value.link_article_with_tags = AsyncMock()

        repo = ArticlesRepository(mock_conn)
        article = await repo.create_article(
            slug="test-article",
            title="Test Article",
            description="A test article",
            body="Article body content",
            author=mock_user,
            tags=["python"],
        )

    assert article.slug == "test-article"
    assert article.title == "Test Article"


@pytest.mark.asyncio
async def test_update_article(mock_conn, mock_article):
    """update_article — 更新文章"""
    with patch("app.db.repositories.articles.queries") as mock_queries:
        mock_queries.update_article = AsyncMock(
            return_value={"updated_at": datetime(2024, 6, 1)}
        )

        repo = ArticlesRepository(mock_conn)
        updated = await repo.update_article(
            article=mock_article,
            title="Updated Title",
        )

    assert updated.title == "Updated Title"
    assert updated.slug == "test-article"  # 未修改的字段保持不变


@pytest.mark.asyncio
async def test_delete_article(mock_conn, mock_article):
    """delete_article — 删除文章"""
    with patch("app.db.repositories.articles.queries") as mock_queries:
        mock_queries.delete_article = AsyncMock()

        repo = ArticlesRepository(mock_conn)
        await repo.delete_article(article=mock_article)

    mock_queries.delete_article.assert_called_once_with(
        mock_conn,
        slug="test-article",
        author_username="author",
    )


@pytest.mark.asyncio
async def test_filter_articles_empty(mock_conn):
    """filter_articles — 无文章时返回空列表"""
    with patch("app.db.repositories.articles.queries") as mock_queries:
        mock_conn.fetch = AsyncMock(return_value=[])

        repo = ArticlesRepository(mock_conn)
        articles = await repo.filter_articles()

    assert articles == []


@pytest.mark.asyncio
async def test_get_articles_for_user_feed(mock_conn, mock_article_row):
    """get_articles_for_user_feed — 获取关注 Feed"""
    from app.models.domain.users import UserInDB

    mock_user = UserInDB(
        id=1,
        username="testuser",
        email="test@test.com",
        salt="salt",
        hashed_password="hashed",
        bio="",
        image=None,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )

    with patch("app.db.repositories.articles.queries") as mock_queries, \
         patch("app.db.repositories.articles.ProfilesRepository") as MockProfilesRepo, \
         patch("app.db.repositories.articles.TagsRepository") as MockTagsRepo:
        mock_queries.get_articles_for_feed = AsyncMock(return_value=[mock_article_row])
        # ★ 改造后走的是"批量"方法：一次查一批文章
        mock_queries.get_favorites_count_for_articles = AsyncMock(
            return_value=[{"slug": "test-article", "favorites_count": 0}]
        )
        # 登录用户会多查一次"我收藏了哪几篇"
        mock_queries.get_favorited_slugs_for_user = AsyncMock(return_value=[])
        MockProfilesRepo.return_value.get_profiles_by_usernames = AsyncMock(
            return_value={
                "author": Profile(username="author", bio="", image=None, following=False)
            }
        )
        MockTagsRepo.return_value.get_tags_for_articles = AsyncMock(
            return_value={"test-article": []}
        )

        repo = ArticlesRepository(mock_conn)
        articles = await repo.get_articles_for_user_feed(user=mock_user)

    assert len(articles) == 1
    assert articles[0].slug == "test-article"
