-- name: get_comments_for_article
-- 获取文章的所有评论（按时间排序）
SELECT id, body, author_id, article_id, created_at, updated_at
FROM comments
WHERE article_id = :article_id
ORDER BY created_at ASC;


-- name: create_comment<!
-- 创建评论
INSERT INTO comments (body, author_id, article_id)
VALUES (:body, :author_id, :article_id)
RETURNING id, body, author_id, article_id, created_at, updated_at;


-- name: delete_comment!
-- 删除评论
DELETE FROM comments
WHERE id = :comment_id AND author_id = :author_id;