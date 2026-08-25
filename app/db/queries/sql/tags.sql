-- name: get_tags_for_article
SELECT t.tag
FROM tags t
JOIN articles_to_tags att ON t.tag = att.tag
WHERE att.article_id = :article_id;


-- name: create_tag!
-- 创建标签（如果不存在）
INSERT INTO tags (tag) VALUES (:tag) ON CONFLICT (tag) DO NOTHING;


-- name: link_article_tag!
-- 关联文章与标签
INSERT INTO articles_to_tags (article_id, tag) 
VALUES (:article_id, :tag)
ON CONFLICT (article_id, tag) DO NOTHING;
