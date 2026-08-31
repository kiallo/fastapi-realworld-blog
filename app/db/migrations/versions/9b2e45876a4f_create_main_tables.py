"""create_main_tables

Revision ID: 0001
Revises: None
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None


def upgrade() -> None:
    """创建所有表"""
    # 用户表
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("salt", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("bio", sa.Text, default="", nullable=False),
        sa.Column("image", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 文章表
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # 标签表
    op.create_table(
        "tags",
        sa.Column("tag", sa.String(255), primary_key=True),
    )

    # 文章-标签关联表
    op.create_table(
        "articles_to_tags",
        sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id", ondelete="CASCADE")),
        sa.Column("tag", sa.String(255), sa.ForeignKey("tags.tag", ondelete="CASCADE")),
        sa.PrimaryKeyConstraint("article_id", "tag"),
    )

    # 收藏表
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id", ondelete="CASCADE")),
        sa.PrimaryKeyConstraint("user_id", "article_id"),
    )

    # 关注表
    op.create_table(
        "followers",
        sa.Column("follower_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("following_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.PrimaryKeyConstraint("follower_id", "following_id"),
    )

    # 评论表
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id", ondelete="CASCADE")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """回滚 — 删除所有表"""
    op.drop_table("comments")
    op.drop_table("followers")
    op.drop_table("favorites")
    op.drop_table("articles_to_tags")
    op.drop_table("tags")
    op.drop_table("articles")
    op.drop_table("users")
