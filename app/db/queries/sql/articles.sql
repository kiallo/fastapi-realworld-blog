-- name: get_article_by_slug^
-- 根据 slug 获取文章
SELECT
    id,
    slug,
    title,
    description,
    body,
    author_id,
    created_at,
    updated_at
FROM articles
WHERE slug = :slug;


-- name: create_article<!
-- 创建文章
INSERT INTO articles ( slug, title, description, body, author_id )
VALUES (:slug, :title, :description, :body, :author_id)
RETURNING
    id,
    slug,
    title,
    description,
    body,
    author_id,
    created_at,
    updated_at;


-- name: update_article!
-- 更新文章
UPDATE articles
SET slug = :slug,
    title = :title,
    description = :description,
    body = :body
WHERE slug = :slug AND author_id = :author_id;


-- name: delete_article!
-- 删除文章
DELETE FROM articles
WHERE slug = :slug AND author_id = :author_id;


-- name: get_all_tags
-- 获取所有标签
SELECT DISTINCT tag FROM tags ORDER BY tag;