import redis
import json
from datetime import timedelta


def test_redis_connection():
    """测试 Redis 连接"""
    try:
        # 创建连接
        r = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True  # 自动解码为字符串
        )
        
        # 测试连接
        print(f"PING: {r.ping()}")
        print("✅ Redis 连接成功！")
        return r
    except redis.ConnectionError as e:
        print(f"❌ Redis 连接失败: {e}")
        return None


def test_string_operations(r):
    """测试 String 类型操作"""
    print("\n" + "="*50)
    print("📌 String 类型操作")
    print("="*50)
    
    # 基本操作
    r.set('username', '张三')
    print(f"GET username: {r.get('username')}")
    
    # 设置过期时间
    r.set('session:abc', 'user_data', ex=60)  # 60秒过期
    print(f"Session TTL: {r.ttl('session:abc')} 秒")
    
    # 自增操作
    r.set('view_count', 100)
    r.incr('view_count')
    r.incr('view_count')
    r.incrby('view_count', 10)
    print(f"View Count: {r.get('view_count')}")
    
    # 批量操作
    r.mset({'key1': 'value1', 'key2': 'value2', 'key3': 'value3'})
    values = r.mget('key1', 'key2', 'key3')
    print(f"MGET: {values}")


def test_hash_operations(r):
    """测试 Hash 类型操作"""
    print("\n" + "="*50)
    print("📌 Hash 类型操作")
    print("="*50)
    
    # 设置哈希表
    r.hset('user:1', mapping={
        'name': '张三',
        'email': 'zhangsan@example.com',
        'age': 25
    })
    
    # 获取单个字段
    print(f"Name: {r.hget('user:1', 'name')}")
    
    # 获取所有字段
    user_data = r.hgetall('user:1')
    print(f"User Data: {user_data}")
    
    # 自增字段
    r.hincrby('user:1', 'age', 1)
    print(f"Age after incr: {r.hget('user:1', 'age')}")


def test_list_operations(r):
    """测试 List 类型操作"""
    print("\n" + "="*50)
    print("📌 List 类型操作")
    print("="*50)
    
    # 清空列表
    r.delete('articles')
    
    # 推入元素
    r.lpush('articles', '文章3', '文章2', '文章1')
    r.rpush('articles', '文章4', '文章5')
    
    # 获取列表长度
    print(f"List Length: {r.llen('articles')}")
    
    # 获取所有元素
    articles = r.lrange('articles', 0, -1)
    print(f"All Articles: {articles}")
    
    # 弹出元素
    print(f"LPOP: {r.lpop('articles')}")
    print(f"RPOP: {r.rpop('articles')}")


def test_set_operations(r):
    """测试 Set 类型操作"""
    print("\n" + "="*50)
    print("📌 Set 类型操作")
    print("="*50)
    
    # 清空集合
    r.delete('tags')
    
    # 添加元素
    r.sadd('tags', 'Python', 'FastAPI', 'Redis', 'Docker')
    
    # 获取所有元素
    tags = r.smembers('tags')
    print(f"Tags: {tags}")
    
    # 判断元素是否存在
    print(f"Has Python: {r.sismember('tags', 'Python')}")
    print(f"Has Java: {r.sismember('tags', 'Java')}")
    
    # 集合运算
    r.sadd('user:1:tags', 'Python', 'FastAPI', 'Redis')
    r.sadd('user:2:tags', 'Python', 'Docker', 'PostgreSQL')
    
    # 交集
    common_tags = r.sinter('user:1:tags', 'user:2:tags')
    print(f"Common Tags: {common_tags}")


def test_sorted_set_operations(r):
    """测试 Sorted Set 类型操作"""
    print("\n" + "="*50)
    print("📌 Sorted Set 类型操作")
    print("="*50)
    
    # 清空有序集合
    r.delete('hot_articles')
    
    # 添加元素（带分数）
    r.zadd('hot_articles', {
        'FastAPI入门': 100,
        'Redis教程': 200,
        'Docker实战': 150,
        'Python进阶': 300
    })
    
    # 获取所有元素（按分数排序）
    articles = r.zrange('hot_articles', 0, -1, withscores=True)
    print(f"Hot Articles: {articles}")
    
    # 获取前3名（从高到低）
    top3 = r.zrevrange('hot_articles', 0, 2, withscores=True)
    print(f"Top 3: {top3}")
    
    # 自增分数
    r.zincrby('hot_articles', 50, 'FastAPI入门')
    print(f"FastAPI new score: {r.zscore('hot_articles', 'FastAPI入门')}")
    
    # 获取排名
    rank = r.zrevrank('hot_articles', 'Redis教程')
    print(f"Redis教程排名: {rank + 1}")


def test_pipeline(r):
    """测试 Pipeline（批量操作）"""
    print("\n" + "="*50)
    print("📌 Pipeline 批量操作")
    print("="*50)
    
    # 使用 Pipeline 批量执行命令
    pipe = r.pipeline()
    
    # 添加多个命令
    for i in range(10):
        pipe.set(f'key:{i}', f'value:{i}')
    
    # 执行所有命令
    results = pipe.execute()
    print(f"Pipeline executed {len(results)} commands")
    
    # 验证
    print(f"key:0 = {r.get('key:0')}")
    print(f"key:9 = {r.get('key:9')}")


def test_transaction(r):
    """测试事务"""
    print("\n" + "="*50)
    print("📌 事务操作")
    print("="*50)
    
    # 使用事务
    with r.pipeline() as pipe:
        while True:
            try:
                # 监视键（乐观锁）
                pipe.watch('balance')
                
                # 获取当前余额
                balance = int(pipe.get('balance') or 100)
                print(f"Current balance: {balance}")
                
                # 开始事务
                pipe.multi()
                
                # 扣减余额
                pipe.decrby('balance', 30)
                pipe.incrby('spent', 30)
                
                # 执行事务
                pipe.execute()
                print("Transaction committed!")
                break
                
            except redis.WatchError:
                print("Balance changed, retrying...")
                continue


if __name__ == "__main__":
    # 测试连接
    r = test_redis_connection()
    if r:
        # 测试各种操作
        test_string_operations(r)
        test_hash_operations(r)
        test_list_operations(r)
        test_set_operations(r)
        test_sorted_set_operations(r)
        test_pipeline(r)
        test_transaction(r)
        
        print("\n" + "="*50)
        print("✅ 所有测试完成！")
        print("="*50)