"""Prometheus 指标定义。

⚠️ 所有指标对象必须是**模块级单例**。

prometheus_client 把指标注册进一个全局 REGISTRY，同名注册两次会抛
    ValueError: Duplicated timeseries in CollectorRegistry
而 tests/conftest.py 的 app fixture 每个用例都调 get_application()。
如果把 Counter(...) 写在函数或类里，第 2 个用例就会炸 —— 报错信息还完全看不出是这个原因。

同理：这个模块只能 import 标准库和 prometheus_client，
不要 import app 里的任何东西，否则容易和 core 下的模块绕成循环 import。
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------- ① Counter
# 只增不减。用来算 QPS（rate）和错误率。重启会归零，这是设计如此。
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP 请求总数",
    labelnames=("method", "path", "status"),
)

# ---------------------------------------------------------------- ② Histogram
# 分布。用来算 P50/P95/P99。
#
# 桶是自定义的，不是默认值。默认桶从 0.005 起、到 10 秒，粒度太粗：
# 你的接口大部分在 5～50ms，默认桶会把它们全塞进 (0.005, 0.01] 和 (0.01, 0.025] 两个桶里，
# histogram_quantile 插值出来的 P95 会有几十个百分点的误差。
#
# 这里的桶是"按你实际的量级加密"：10/25/50/75/100ms 各一档。
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求耗时（秒）",
    labelnames=("method", "path", "status"),
    buckets=(
        0.005, 0.01, 0.025, 0.05, 0.075,
        0.1, 0.15, 0.2, 0.3, 0.5,
        0.75, 1.0, 2.0, 5.0,
    ),
)

# ---------------------------------------------------------------- ③ Gauge
# 可增可减。用来判断"是不是被打满了"。
HTTP_IN_FLIGHT = Gauge(
    "http_requests_in_flight",
    "当前正在处理的请求数",
)

# ---------------------------------------------------------------- ④ 缓存
# 不是 RED 的一部分，但它能把"缓存到底有没有用"变成一个可查的数字，
# 而不是靠日志里那句 "✅ 缓存命中" 去数。
CACHE_REQUESTS_TOTAL = Counter(
    "cache_requests_total",
    "缓存访问次数",
    labelnames=("cache", "result"),   # result: hit | miss | error
)