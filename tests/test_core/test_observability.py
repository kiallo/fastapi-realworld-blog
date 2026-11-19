"""观测中间件的测试。

四个断言对应四种"静默失效"：
  路由没挂上、计数器没涨、标签用了真实路径、request_id 复用。
这四种都不会让接口报错，只会让你在某天需要数据时发现它是空的。
"""

from prometheus_client import REGISTRY


def _value(name: str, labels: dict) -> float:
    """读一个样本的当前值，不存在时返回 0。

    ⚠️ 必须用"改前/改后取差"的方式断言，不能断言等于某个绝对值：
       指标是全局单例（见 4.6），别的用例已经打过请求，绝对值不可预测。
    """
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_metrics_endpoint_exposed(client):
    """① /metrics 能抓，且含我们自己的指标名"""
    # ⚠️ 必须先打一个请求：Histogram 在"没有任何观测值"时只输出 HELP/TYPE，
    #    不会输出 *_bucket 样本行。少了这一句，这个用例单独跑会红、全量跑会绿。
    await client.get("http://testserver/api/ping")

    resp = await client.get("http://testserver/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds_bucket" in body


async def test_counter_increases_after_request(client):
    """② 打一次接口，对应标签的计数 +1"""
    labels = {"method": "GET", "path": "/api/ping", "status": "200"}
    before = _value("http_requests_total", labels)

    resp = await client.get("http://testserver/api/ping")
    assert resp.status_code == 200

    assert _value("http_requests_total", labels) == before + 1


async def test_slug_is_not_used_as_label(client):
    """③ 标签用路由模板，不用真实 URL —— 这条防的是基数爆炸"""
    slug = "this-slug-must-not-become-a-label"
    before = _value(
        "http_requests_total",
        {"method": "GET", "path": "/api/articles/{slug}", "status": "404"},
    )

    resp = await client.get(f"http://testserver/api/articles/{slug}")
    assert resp.status_code == 404

    # 模板标签涨了
    assert (
        _value(
            "http_requests_total",
            {"method": "GET", "path": "/api/articles/{slug}", "status": "404"},
        )
        == before + 1
    )
    # 真实路径**没有**成为标签
    assert (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "path": f"/api/articles/{slug}", "status": "404"},
        )
        is None
    )


async def test_request_id_header_is_unique(client):
    """④ 每个请求一个 ID，且回给客户端"""
    r1 = await client.get("http://testserver/api/ping")
    r2 = await client.get("http://testserver/api/ping")

    id1 = r1.headers.get("x-request-id")
    id2 = r2.headers.get("x-request-id")

    assert id1 and id2
    assert id1 != id2
    assert len(id1) == 32  # uuid4().hex


async def test_in_flight_returns_to_zero(client):
    """⑤ 在飞请求数要回落 —— Gauge 忘了 dec() 时它会一直涨，图上看不出来"""
    await client.get("http://testserver/api/ping")
    assert _value("http_requests_in_flight", {}) == 0
