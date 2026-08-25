-- name: add_to_favorites!
-- 收藏文章
INSERT INTO favorites (user_id, article_id) 
VALUES (:user_id, :article_id);


-- name: remove_from_favorites!
-- 取消收藏
DELETE FROM favorites WHERE user_id = :user_id AND article_id = :article_id;


-- name: is_article_favorited^
-- 检查文章是否被收藏
SELECT EXISTS(
    SELECT 1 FROM favorites WHERE user_id = :user_id AND article_id = :article_id
) AS favorited;