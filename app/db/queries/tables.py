from pypika import Table, Query, Parameter, CustomFunction


# ===== 自定义 Parameter：适配 asyncpg 的 $1, $2... 占位符 =====
class AsyncpgParameter(Parameter):
    def __init__(self, index: int) -> None:
        super().__init__(f"${index + 1}")


# ===== 表定义（Typed Table）=====
class Users(Table):
    __table__ = "users"

    id: int
    username: str
    email: str
    salt: str
    hashed_password: str
    bio: str
    image: str
    created_at: str
    updated_at: str


class Articles(Table):
    __table__ = "articles"

    id: int
    slug: str
    title: str
    description: str
    body: str
    author_id: int
    created_at: str
    updated_at: str


class Tags(Table):
    __table__ = "tags"
    tag: str


class ArticlesToTags(Table):
    __table__ = "articles_to_tags"
    article_id: int
    tag: str


class Favorites(Table):
    __table__ = "favorites"
    user_id: int
    article_id: int


class Followers(Table):
    __table__ = "followers"
    follower_id: int
    following_id: int


class Comments(Table):
    __table__ = "comments"
    id: int
    body: str
    author_id: int
    article_id: int
    created_at: str
    updated_at: str



# ===== 模块级单例 =====
users = Users("users")
articles = Articles("articles")
tags = Tags("tags")
articles_to_tags = ArticlesToTags("articles_to_tags")
favorites = Favorites("favorites")
followers = Followers("followers")
comments_table = Comments("comments")