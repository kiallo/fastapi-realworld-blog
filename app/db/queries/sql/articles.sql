-- name: get_article_by_slug^
-- 根据 slug 获取文章
SELECT a.id, a.slug, a.title, a.description, a.body,
       a.created_at, a.updated_at,
       (SELECT username FROM users WHERE id = a.author_id) AS author_username
FROM articles a
WHERE a.slug = :slug;


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


-- name: update_article<!
-- 更新文章（通过 slug + username 定位，返回更新时间）
UPDATE articles
SET slug        = :new_slug,
    title       = :new_title,
    body        = :new_body,
    description = :new_description,
    updated_at  = now()                     
WHERE slug = :slug
  AND author_id = (SELECT id FROM users WHERE username = :author_username)
RETURNING updated_at;


-- name: delete_article!
-- 删除文章（通过 slug + username 定位）
DELETE FROM articles
WHERE slug = :slug
  AND author_id = (SELECT id FROM users WHERE username = :author_username);


-- name: get_articles_for_feed
-- 获取关注用户的文章 Feed
SELECT a.id,
       a.slug,
       a.title,
       a.description,
       a.body,
       a.created_at,
       a.updated_at,
       (SELECT username FROM users WHERE id = a.author_id) AS author_username
FROM articles a
         INNER JOIN followers f ON
        f.following_id = a.author_id
        AND f.follower_id = (SELECT id FROM users WHERE username = :follower_username)
ORDER BY a.created_at DESC
LIMIT :limit
OFFSET :offset;


-- name: get_tags_for_article_by_slug
-- 通过文章 slug 获取标签列表
SELECT t.tag
FROM tags t
         INNER JOIN articles_to_tags att ON
        t.tag = att.tag
        AND att.article_id = (SELECT id FROM articles WHERE slug = :slug);


-- name: add_tags_to_article*!
-- 批量添加标签到文章
INSERT INTO articles_to_tags (article_id, tag)
VALUES ((SELECT id FROM articles WHERE slug = :slug),
        (SELECT tag FROM tags WHERE tag = :tag))
ON CONFLICT DO NOTHING;


-- name: get_favorites_count_for_article^
-- 获取文章收藏数
SELECT count(*) AS favorites_count
FROM favorites
WHERE article_id = (SELECT id FROM articles WHERE slug = :slug);


-- name: is_article_in_favorites^
-- 检查用户是否收藏了文章（通过 username）
SELECT CASE WHEN count(user_id) > 0 THEN TRUE ELSE FALSE END AS favorited
FROM favorites
WHERE user_id = (SELECT id FROM users WHERE username = :username)
  AND article_id = (SELECT id FROM articles WHERE slug = :slug);


-- name: add_article_to_favorites!
-- 收藏文章（通过 username）
INSERT INTO favorites (user_id, article_id)
VALUES ((SELECT id FROM users WHERE username = :username),
        (SELECT id FROM articles WHERE slug = :slug))
ON CONFLICT DO NOTHING;


-- name: remove_article_from_favorites!
-- 取消收藏（通过 username）
DELETE FROM favorites
WHERE user_id = (SELECT id FROM users WHERE username = :username)
  AND article_id = (SELECT id FROM articles WHERE slug = :slug);


-- name: get_all_tags
-- 获取所有标签
SELECT DISTINCT tag FROM tags ORDER BY tag;


-- name: get_tags_for_articles_by_slugs
-- ★ 批量版：一次性取回多篇文章的标签（消 N+1）
SELECT a.slug, t.tag
FROM articles a
         INNER JOIN articles_to_tags att ON att.article_id = a.id
         INNER JOIN tags t ON t.tag = att.tag
WHERE a.slug = ANY(:slugs::text[]);


-- name: get_favorites_count_for_articles
-- ★ 批量版：一次性取回多篇文章的收藏数（消 N+1）
-- ⚠️ 必须用 LEFT JOIN：没人收藏的文章也要出现在结果里（收藏数 0）
SELECT a.slug, count(f.user_id)::int AS favorites_count
FROM articles a
         LEFT JOIN favorites f ON f.article_id = a.id
WHERE a.slug = ANY(:slugs::text[])
GROUP BY a.slug;


-- name: get_favorited_slugs_for_user
-- ★ 批量版：一次性取回"这个用户收藏了这批文章里的哪几篇"（消 N+1）
-- 只返回收藏了的 slug，没收藏的不会出现在结果里 —— 调用方用集合判断
SELECT a.slug
FROM articles a
         INNER JOIN favorites f ON f.article_id = a.id
         INNER JOIN users u ON u.id = f.user_id
WHERE u.username = :username
  AND a.slug = ANY(:slugs::text[]);