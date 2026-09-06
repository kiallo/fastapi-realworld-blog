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


-- name: get_comments_for_article_by_slug
-- 通过文章 slug 获取评论列表（联表查询，返回作者用户名）
SELECT c.id,
       c.body,
       c.created_at,
       c.updated_at,
       (SELECT username FROM users WHERE id = c.author_id) AS author_username
FROM comments c
         INNER JOIN articles a ON c.article_id = a.id
WHERE a.slug = :slug
ORDER BY c.created_at ASC;


-- name: get_comment_by_id_and_slug^
-- 通过评论 ID + 文章 slug 获取单条评论
SELECT c.id,
       c.body,
       c.created_at,
       c.updated_at,
       (SELECT username FROM users WHERE id = c.author_id) AS author_username
FROM comments c
         INNER JOIN articles a ON c.article_id = a.id
WHERE c.id = :comment_id
  AND a.slug = :article_slug;


-- name: create_new_comment<!
-- 创建评论（通过 slug 定位文章，返回作者用户名）
WITH author_subquery AS (
    SELECT id, username FROM users WHERE username = :author_username
)
INSERT INTO comments (body, author_id, article_id)
VALUES (:body,
        (SELECT id FROM author_subquery),
        (SELECT id FROM articles WHERE slug = :article_slug))
RETURNING
    id,
    body,
    (SELECT username FROM author_subquery) AS author_username,
    created_at,
    updated_at;


-- name: delete_comment_by_slug!
-- 删除评论（通过 slug 定位文章 + 只能删除自己的评论）
DELETE FROM comments
WHERE id = :comment_id
  AND author_id = (SELECT id FROM users WHERE username = :author_username);