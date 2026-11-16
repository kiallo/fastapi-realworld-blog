"""密码哈希与校验：salt 随机性、bcrypt 往返、错误密码、格式。

纯函数测试，不碰数据库、不碰 Redis。
"""
from app.services.security import generate_salt, get_password_hash, verify_password


def test_salt_is_random_per_call():
    """salt 必须每次不同，否则同一个密码在库里会长得一样"""
    assert generate_salt() != generate_salt()


def test_hash_and_verify_roundtrip():
    salt = generate_salt()
    hashed = get_password_hash(salt, "pass12345")

    assert hashed != "pass12345"
    assert verify_password(salt=salt, password="pass12345", hashed_password=hashed) is True


def test_wrong_password_fails_verification():
    salt = generate_salt()
    hashed = get_password_hash(salt, "pass12345")

    assert verify_password(salt=salt, password="wrong-pass", hashed_password=hashed) is False


def test_same_password_different_salt_gives_different_hash():
    """加盐的意义：同一个密码 + 不同盐 = 不同哈希，彩虹表失效"""
    h1 = get_password_hash(generate_salt(), "same-password")
    h2 = get_password_hash(generate_salt(), "same-password")

    assert h1 != h2


def test_hash_format_is_bcrypt():
    """bcrypt 哈希以 $2b$ 开头，salt 和 cost 都嵌在里面"""
    hashed = get_password_hash(generate_salt(), "x")

    assert hashed.startswith("$2b$")
    assert len(hashed) == 60
