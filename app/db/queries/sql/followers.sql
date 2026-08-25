-- name: follow_user!
INSERT INTO followers (follower_id, following_id) VALUES (:follower_id, :following_id);


-- name: unfollow_user!
DELETE FROM followers WHERE follower_id = :follower_id AND following_id = :following_id;


-- name: is_user_following^
SELECT EXISTS(
    SELECT 1 FROM followers WHERE follower_id = :follower_id AND following_id = :following_id
) AS following;