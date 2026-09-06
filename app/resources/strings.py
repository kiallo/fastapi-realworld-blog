"""所有错误消息和提示文字的集中管理"""

# 认证相关
INCORRECT_LOGIN_INPUT = "邮箱或密码错误"
USERNAME_TAKEN = "用户名已被占用"
EMAIL_TAKEN = "邮箱已被注册"
AUTHENTICATION_REQUIRED = "需要认证"
INVALID_TOKEN = "Token 无效或已过期"
NO_PERMISSION = "你没有权限执行此操作"

# 用户相关
USER_DOES_NOT_EXIST_ERROR = "用户不存在"

# 文章相关
ARTICLE_DOES_NOT_EXIST = "文章不存在"
ARTICLE_ALREADY_EXISTS = "文章已存在"

# 评论相关
COMMENT_DOES_NOT_EXIST = "评论不存在"
USER_IS_NOT_AUTHOR_OF_ARTICLE = "你不是该内容的作者，无权操作"

# 关注相关
CANNOT_FOLLOW_YOURSELF = "不能关注自己"

# 收藏相关
ALREADY_FAVORITED = "你已经收藏过这篇文章"
ARTICLE_IS_NOT_FAVORITED = "你还没有收藏这篇文章"