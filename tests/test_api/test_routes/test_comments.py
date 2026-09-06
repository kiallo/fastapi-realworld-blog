"""评论 Repository 测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.db.repositories.comments import CommentsRepository
from app.models.domain.comments import Comment
from app.models.domain.profiles import Profile
from app.models.domain.articles import Article


@pytest.fixture
def mock_conn():
    """模拟数据库连接"""
    return MagicMock()


@pytest.fixture
def mock_article():
    return Article(
        id=1,
        slug="test-article",
        title="Test Article",
        description="Test desc",
        body="Test body",
        author=Profile(username="author", bio="", image=None, following=False),
        tags=[],
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def mock_comment_row():
    """模拟数据库返回的评论行"""
    return {
        "id": 1,
        "body": "测试评论内容",
        "author_username": "testuser",
        "created_at": datetime(2024, 1, 1),
        "updated_at": datetime(2024, 1, 1),
    }


@pytest.mark.asyncio
async def test_get_comments_for_article(mock_conn, mock_article, mock_comment_row):
    """get_comments_for_article — 获取文章评论列表"""
    with patch("app.db.repositories.comments.queries") as mock_queries, \
         patch("app.db.repositories.comments.ProfilesRepository") as MockProfilesRepo:
        mock_queries.get_comments_for_article_by_slug = AsyncMock(
            return_value=[mock_comment_row]
        )
        mock_profile = Profile(username="testuser", bio="", image=None, following=False)
        MockProfilesRepo.return_value.get_profile_by_username = AsyncMock(
            return_value=mock_profile
        )

        repo = CommentsRepository(mock_conn)
        comments = await repo.get_comments_for_article(article=mock_article)

    assert len(comments) == 1
    assert comments[0].body == "测试评论内容"
    assert comments[0].author.username == "testuser"


@pytest.mark.asyncio
async def test_get_comment_by_id(mock_conn, mock_article, mock_comment_row):
    """get_comment_by_id — 获取单条评论"""
    with patch("app.db.repositories.comments.queries") as mock_queries, \
         patch("app.db.repositories.comments.ProfilesRepository") as MockProfilesRepo:
        mock_queries.get_comment_by_id_and_slug = AsyncMock(
            return_value=mock_comment_row
        )
        mock_profile = Profile(username="testuser", bio="", image=None, following=False)
        MockProfilesRepo.return_value.get_profile_by_username = AsyncMock(
            return_value=mock_profile
        )

        repo = CommentsRepository(mock_conn)
        comment = await repo.get_comment_by_id(
            comment_id=1, article=mock_article
        )

    assert comment.id == 1
    assert comment.body == "测试评论内容"


@pytest.mark.asyncio
async def test_get_comment_by_id_not_found(mock_conn, mock_article):
    """get_comment_by_id — 评论不存在时抛异常"""
    from app.db.errors import EntityDoesNotExist

    with patch("app.db.repositories.comments.queries") as mock_queries:
        mock_queries.get_comment_by_id_and_slug = AsyncMock(return_value=None)

        repo = CommentsRepository(mock_conn)
        with pytest.raises(EntityDoesNotExist):
            await repo.get_comment_by_id(comment_id=999, article=mock_article)


@pytest.mark.asyncio
async def test_create_comment_for_article(mock_conn, mock_article, mock_comment_row):
    """create_comment_for_article — 创建评论"""
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

    with patch("app.db.repositories.comments.queries") as mock_queries, \
         patch("app.db.repositories.comments.ProfilesRepository") as MockProfilesRepo:
        mock_queries.create_new_comment = AsyncMock(return_value=mock_comment_row)
        mock_profile = Profile(username="testuser", bio="", image=None, following=False)
        MockProfilesRepo.return_value.get_profile_by_username = AsyncMock(
            return_value=mock_profile
        )

        repo = CommentsRepository(mock_conn)
        comment = await repo.create_comment_for_article(
            body="测试评论内容",
            article=mock_article,
            user=mock_user,
        )

    assert comment.body == "测试评论内容"
    assert comment.author.username == "testuser"
    mock_queries.create_new_comment.assert_called_once()


@pytest.mark.asyncio
async def test_delete_comment(mock_conn, mock_article):
    """delete_comment — 删除评论"""
    comment = Comment(
        id=1,
        body="test",
        author=Profile(username="testuser", bio="", image=None, following=False),
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )

    with patch("app.db.repositories.comments.queries") as mock_queries:
        mock_queries.delete_comment_by_slug = AsyncMock()

        repo = CommentsRepository(mock_conn)
        await repo.delete_comment(comment=comment)

    mock_queries.delete_comment_by_slug.assert_called_once_with(
        mock_conn,
        comment_id=1,
        author_username="testuser",
    )
