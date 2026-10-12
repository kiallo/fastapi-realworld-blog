-- name: get_user_by_email^
-- 根据邮箱查询用户，返回单行
SELECT
    id,
    username,
    email,
    salt,
    hashed_password,
    bio,
    image,
    created_at,
    updated_at
FROM users
WHERE email = :email;


-- name: get_user_by_username^
-- 根据用户名查询用户
SELECT
    id,
    username,
    email,
    salt,
    hashed_password,
    bio,
    image,
    created_at,
    updated_at
FROM users
WHERE username = :username;


-- name: create_new_user<!
-- 创建新用户，返回新插入的行
INSERT INTO
    users (
        username,
        email,
        salt,
        hashed_password,
        bio,
        image
    )
VALUES (:username, :email, :salt, :hashed_password, :bio, :image)
RETURNING
    id,
    username,
    email,
    salt,
    hashed_password,
    bio,
    image,
    created_at,
    updated_at;


-- name: update_user_by_email!
-- 更新用户资料
UPDATE users
SET username = :username,
    email = :email,
    salt = :salt,
    hashed_password = :hashed_password,
    bio = :bio,
    image = :image,
    updated_at = NOW()
WHERE email = :email;


-- name: get_all_user_ids
-- 获取所有用户 ID（测试用）
SELECT id FROM users;


-- name: get_users_by_usernames
-- ★ 批量版：一次性取回多个用户的公开资料（消 N+1）
-- 只取公开字段（不含 salt / hashed_password）—— 和 Profile 的字段对齐
SELECT id, username, bio, image
FROM users
WHERE username = ANY(:usernames::text[]);