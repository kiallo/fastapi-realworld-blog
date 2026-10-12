-- name: follow_user!
INSERT INTO followers (follower_id, following_id) VALUES (:follower_id, :following_id);


-- name: unfollow_user!
DELETE FROM followers WHERE follower_id = :follower_id AND following_id = :following_id;


-- name: is_user_following^
SELECT EXISTS(
    SELECT 1 FROM followers WHERE follower_id = :follower_id AND following_id = :following_id
) AS following;


-- name: subscribe_user_to_another!
-- 通过用户名关注用户
INSERT INTO followers (follower_id, following_id)
VALUES (
    (SELECT id FROM users WHERE username = :follower_username),
    (SELECT id FROM users WHERE username = :following_username)
);


-- name: unsubscribe_user_from_another!
-- 通过用户名取消关注
DELETE FROM followers
WHERE follower_id = (SELECT id FROM users WHERE username = :follower_username)
  AND following_id = (SELECT id FROM users WHERE username = :following_username);


-- name: is_user_following_for_another^
-- 通过用户名检查关注状态
SELECT CASE
    WHEN following_id IS NULL THEN FALSE
    ELSE TRUE
END AS is_following
FROM users u
    LEFT OUTER JOIN followers f ON u.id = f.follower_id
        AND f.following_id = (
            SELECT id FROM users WHERE username = :following_username
        )
WHERE u.username = :follower_username
LIMIT 1;


-- name: get_following_usernames_for_user
-- ★ 批量版：一次性取回"这个用户关注了这批作者里的哪几个"（消 N+1）
-- 只返回已关注的用户名，没关注的不会出现在结果里 —— 调用方用集合判断
SELECT u.username
FROM users u
         INNER JOIN followers f ON f.following_id = u.id
WHERE f.follower_id = (SELECT id FROM users WHERE username = :follower_username)
  AND u.username = ANY(:usernames::text[]);