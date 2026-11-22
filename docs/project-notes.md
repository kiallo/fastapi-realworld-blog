# 项目说明：FastAPI RealWorld 博客（含可观测性与权限扩展）

## 一句话

一个分层架构的 RealWorld 博客后端（FastAPI + PostgreSQL + Redis），
在基础功能之上补了四件事：可观测性（日志/指标/面板）、压测与优化、RBAC 权限、异步任务与幂等。

## 架构

请求链路：`uvicorn → ObservabilityMiddleware → LoggingMiddleware → TimingMiddleware → 路由 → 仓储 → asyncpg/Redis`

| 层 | 位置 | 职责 |
|---|---|---|
| 路由 | `app/api/routes/` | 只做参数校验与拼装，不写业务 |
| 依赖 | `app/api/dependencies/` | 认证、权限、从路径取实体 |
| 仓储 | `app/db/repositories/` | SQL 全部走 `app/db/queries/sql/*.sql`（aiosql） |
| 服务 | `app/services/` | LLM 摘要、JWT、密码、会话存储 |
| 基础设施 | `app/core/` | 缓存、指标、中间件、配置、任务存储 |

## 三个关键决策（面试重点）

**1. 角色存数据库，权限写代码。**
`users.role` 一列（reader/author/admin），权限映射在 `app/core/permissions.py`。
理由：权限点就是接口端点，端点在代码里；权限进数据库只会多一个"库和代码不同步"的故障源。
代价：一个用户多角色这个需求一旦出现，要做数据迁移。

**2. 异步任务用 Redis，不用 Celery。**
单进程、单次任务 < 20 秒、没有跨机器调度需求。上 Celery 要多一个 broker + worker 进程 + 一套部署。
代价：进程重启丢在飞任务，靠 `summary:active` 的 TTL 自愈。

**3. 缓存只优化中位数，不解决尾延迟。**
详情接口加缓存后 P50 从 9.5ms 降到 7.4ms（−22%），但 **P95 纹丝不动**（18.2–20.8 → 18.5–21.9）。
结论：尾延迟不来自 PostgreSQL，而来自 50 个 VU 争抢一个事件循环。
**这条"没提升"的结论比"提升了 22%"更值钱**，因为它排除了一个方向。

## 数字（全部可回溯）

| 指标 | 数值 | 口径 | 出处 |
|---|---|---|---|
| 详情接口 P50（缓存前 → 后） | 9.3–9.8 → 7.1–7.8 ms | 50 VU / think 0.2s | `docs/loadtest-report.md` |
| 详情接口 P95（缓存前 → 后） | 18.2–20.8 → 18.5–21.9 ms（无变化） | 同上 | 同上 |
| 缓存命中率 | 99.97%（34614/34623） | 单轮 | `/metrics` |
| 列表接口 P95 @50 VU | 20.2 ms | 同上 | `docs/baseline.md` |
| 100 VU 吞吐平台 | ~375 QPS | 同上 | `docs/baseline.md` |
| 同配置波动 | QPS 极差 1.45% | 3 次连跑 | `docs/baseline.md` |
| 测试 | 116 passed / 覆盖率 73% | `pytest -q --cov` | 本地 |

⚠️ 数据来自本机（Windows 11 / Ryzen 7 8845H / 8 核），压测端与被测端同机，
绝对值偏低，但**前后对比的差值仍有效**。

## 没做的事（主动说明）

| 项 | 为什么没做 |
|---|---|
| 多租户 / 行级隔离 | 单租户博客没有这个需求，硬做是编需求 |
| 审计日志 | 只做了 `authz_denied_total` 计数；完整审计要落库 + 保留策略，收益低于成本 |
| Celery / 多 worker | 规模不到，见决策 2 |
| 异步摘要的真实耗时 | 未配 `LLM_API_KEY`，只验证了 202 与任务状态语义，**没测响应耗时** |

## 复现

见 `docs/loadtest-report.md` 第 7 节（起依赖 → 起应用 → 跑 k6）。
测试：`docker compose up -d test-db` + `APP_ENV=test poetry run pytest -q`。