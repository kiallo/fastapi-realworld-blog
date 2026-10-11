"""
文章列表接口压测脚本（异步并发版）

用法（在项目根目录、虚拟环境里）：
    python demos/demo_bench_articles.py
    python demos/demo_bench_articles.py --concurrency 30 --duration 15

依赖：httpx（项目里已经有了，不用额外装）
"""

import argparse
import asyncio
import statistics
import time

import httpx

BASE_URL = "http://127.0.0.1:18000"
TARGET = "/api/articles?limit=20"


async def worker(client: httpx.AsyncClient, deadline: float, stats: dict):
    """一个并发工作协程：不停地打请求，直到超过 deadline"""
    while time.perf_counter() < deadline:
        t0 = time.perf_counter()
        try:
            resp = await client.get(BASE_URL + TARGET)
            ok = resp.status_code == 200
        except Exception:
            ok = False
        cost_ms = (time.perf_counter() - t0) * 1000

        stats["total"] += 1
        if ok:
            stats["ok"] += 1
            stats["latencies"].append(cost_ms)
        else:
            stats["failed"] += 1


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=20, help="并发数")
    parser.add_argument("--duration", type=int, default=10, help="持续秒数")
    args = parser.parse_args()

    stats = {"total": 0, "ok": 0, "failed": 0, "latencies": []}

    # 连接池开到和并发数一样大，避免"建连接"成为瓶颈
    limits = httpx.Limits(
        max_connections=args.concurrency,
        max_keepalive_connections=args.concurrency,
    )

    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        # ★ 预热：先打一发，把 TCP 握手时间排除在统计之外
        try:
            await client.get(BASE_URL + TARGET)
        except Exception as exc:
            print(f"❌ 连不上 {BASE_URL}")
            print(f"   先确认服务已经启动：uvicorn app.main:app --reload --port 18000")
            print(f"   错误详情：{exc}")
            return

        print(f"并发 {args.concurrency}，持续 {args.duration} 秒 …")
        t_start = time.perf_counter()
        deadline = t_start + args.duration
        await asyncio.gather(
            *[worker(client, deadline, stats) for _ in range(args.concurrency)]
        )
        elapsed = time.perf_counter() - t_start

    lat = sorted(stats["latencies"])
    qps = stats["ok"] / elapsed if elapsed else 0.0

    def percentile(p: float) -> float:
        if not lat:
            return 0.0
        idx = min(int(len(lat) * p), len(lat) - 1)
        return lat[idx]

    print()
    print(f"  总请求    : {stats['total']}")
    print(f"  成功      : {stats['ok']}")
    print(f"  失败      : {stats['failed']}")
    print(f"  实际耗时  : {elapsed:.2f} s")
    print(f"  ⭐ QPS     : {qps:.1f}")
    print(f"  平均延迟  : {statistics.mean(lat):.2f} ms")
    print(f"  P95 延迟  : {percentile(0.95):.2f} ms")
    print(f"  P99 延迟  : {percentile(0.99):.2f} ms")


if __name__ == "__main__":
    asyncio.run(main())