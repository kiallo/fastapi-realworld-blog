"""标签 API 测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.repositories.tags import TagsRepository


@pytest.fixture
def mock_conn():
    return MagicMock()


@pytest.mark.asyncio
async def test_get_all_tags(mock_conn):
    """get_all_tags — 获取所有标签"""
    with patch("app.db.repositories.tags.queries") as mock_queries:
        mock_queries.get_all_tags = AsyncMock(return_value=[
            {"tag": "python"},
            {"tag": "fastapi"},
            {"tag": "asyncpg"},
        ])

        repo = TagsRepository(mock_conn)
        tags = await repo.get_all_tags()

    assert tags == ["python", "fastapi", "asyncpg"]


@pytest.mark.asyncio
async def test_get_all_tags_empty(mock_conn):
    """get_all_tags — 无标签时返回空列表"""
    with patch("app.db.repositories.tags.queries") as mock_queries:
        mock_queries.get_all_tags = AsyncMock(return_value=[])

        repo = TagsRepository(mock_conn)
        tags = await repo.get_all_tags()

    assert tags == []


@pytest.mark.asyncio
async def test_create_tags_that_dont_exist(mock_conn):
    """create_tags_that_dont_exist — 批量创建标签（依赖数据库 ON CONFLICT 去重）"""
    with patch("app.db.repositories.tags.queries") as mock_queries:
        mock_queries.create_tag = AsyncMock()

        repo = TagsRepository(mock_conn)
        await repo.create_tags_that_dont_exist(tags=["python", "fastapi", "newtag"])

    # 为每个标签都调用一次 create_tag
    assert mock_queries.create_tag.call_count == 3
    calls = [call[1]["tag"] for call in mock_queries.create_tag.call_args_list]
    assert "python" in calls
    assert "fastapi" in calls
    assert "newtag" in calls


@pytest.mark.asyncio
async def test_get_tags_for_article(mock_conn):
    """get_tags_for_article — 获取文章标签"""
    with patch("app.db.repositories.tags.queries") as mock_queries:
        mock_queries.get_tags_for_article = AsyncMock(return_value=[
            {"tag": "python"},
            {"tag": "web"},
        ])

        repo = TagsRepository(mock_conn)
        tags = await repo.get_tags_for_article(article_id=1)

    assert tags == ["python", "web"]


@pytest.mark.asyncio
async def test_link_article_with_tags(mock_conn):
    """link_article_with_tags — 关联文章和标签"""
    with patch("app.db.repositories.tags.queries") as mock_queries:
        mock_queries.link_article_tag = AsyncMock()

        repo = TagsRepository(mock_conn)
        await repo.link_article_with_tags(article_id=1, tags=["python", "fastapi"])

    assert mock_queries.link_article_tag.call_count == 2
