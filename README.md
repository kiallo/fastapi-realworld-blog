# 项目结构说明

这是一个用 **FastAPI** 实现的 [RealWorld（Conduit 博客后端）](https://github.com/gothinkster/realworld) 示例项目，整体采用清晰的**分层架构**，并在其上扩展了 Redis 缓存、会话管理与一批学习用的演示接口。

---

## 目录总览

```
.
├── .github/            # GitHub 配置（CI：lint.yml、tests.yml）
├── .vscode/            # 编辑器配置
├── app/                # 主应用源码
├── demos/              # 学习/演示与压测脚本
├── scripts/            # 便捷命令脚本
├── tests/              # 测试代码
├── .dockerignore
├── .env.example             # 开发环境变量模板
├── .env.production.example  # 生产环境变量模板
├── .gitignore
├── Dockerfile
├── README.md
├── alembic.ini         # Alembic 数据库迁移配置
├── docker-compose.yml
├── poetry.lock
├── pyproject.toml      # Poetry 依赖管理 + black/isort/mypy 配置
└── setup.cfg           # pytest 配置
```

---

## 一、项目根目录文件

| 文件 | 作用 |
|------|------|
| `pyproject.toml` | **Poetry** 依赖管理文件。运行时依赖：fastapi、uvicorn、pydantic-settings、loguru；数据库：asyncpg、psycopg2-binary、aiosql、pypika、alembic；缓存：redis；安全：passlib、pyjwt；生产：gunicorn、uvicorn-worker。开发依赖：pytest、pytest-asyncio、pytest-cov、httpx、asgi-lifespan、black、isort、mypy、autoflake。另含 black / isort / mypy 配置 |
| `setup.cfg` | **pytest 配置**：`testpaths = tests`、`asyncio_mode = auto`、`addopts = -v --tb=short` |
| `poetry.lock` | Poetry 锁定具体依赖版本的锁文件 |
| `alembic.ini` | **Alembic 数据库迁移**配置，指向迁移脚本目录 `./app/db/migrations` |
| `Dockerfile` | 基于 `python:3.12-slim` 构建应用镜像：装 curl、装 Poetry、`poetry install --without dev`，暴露 18000 |
| `docker-compose.yml` | 编排三个服务：`db`（PostgreSQL 16-alpine，只绑定回环 `127.0.0.1:5432`，带 healthcheck）+ `redis`（redis:7-alpine，容器间用服务名访问）+ `app`（映射 `18000:18000`，`restart: unless-stopped`，启动前先跑 `alembic upgrade head` 再拉起 uvicorn） |
| `.env.example` | 开发环境变量模板（`APP_ENV`、`DATABASE_URL`、`SECRET_KEY`、`REDIS_HOST`、`LLM_*`），复制成 `.env` 使用 |
| `.env.production.example` | 生产环境变量模板（`POSTGRES_PASSWORD`、`SECRET_KEY`），复制成 `.env.production`；该文件已被 `.gitignore` 忽略，不会进版本库 |
| `.dockerignore` | Docker 构建忽略规则 |
| `.gitignore` | Git 忽略规则 |

> 说明：compose 里包含 `redis` 服务，容器之间用服务名 `redis` 访问；
> 本地 Poetry 后端通过 `docker-compose.override.yml` 把 Redis 映射到 `127.0.0.1:6379`。
> `.env` 里必须写 `REDIS_HOST=127.0.0.1`，**不要用 `localhost`**：
> Windows 会优先把它解析成 `::1`，连接会挂到超时，表现为“登录返回 200，
> 但之后所有需要认证的接口都提示会话已失效”。也不要再启动独立的 Redis 容器抢 6379。

---

## 二、`app/` —— 主应用源码

这是核心，按职责分成 6 个子包，体现清晰的**分层架构**：

```
请求 → routes（路由层）→ dependencies（依赖注入）→ services（业务逻辑）
                                       ↓
                              repositories（仓库层）→ queries（SQL）→ PostgreSQL
                                       ↓
                              models/domain（领域模型）· models/schemas（出入参模型）

                        缓存/会话：core/cache.py · services/token_storage.py → Redis
```

### `app/main.py` —— 入口

- `lifespan` 异步上下文管理器（**替代已弃用的 `on_event`**）：
  - 启动时用 asyncpg 建连接池（`min_size=2, max_size=10`），挂到 `app.state.pool`
  - 连不上数据库时：生产（`db_fail_fast=True`）直接抛异常**快速失败**，开发只打警告继续启动
  - 关闭时 `pool.close()`
- `get_application()` 应用工厂：读配置 → 配置日志 → 创建 FastAPI 实例 → 装配中间件（CORS、`TimingMiddleware`、`LoggingMiddleware`）→ 挂载路由 → 注册异常处理器
- 模块级 `app = get_application()`，供 `uvicorn app.main:app` 使用

### `app/api/` —— API 层（对外接口）

- **`routes/`** —— 路由定义：
  - `authentication.py` —— 注册/登录
  - `users.py` —— 用户
  - `profiles.py` —— 用户关注
  - `tags.py` —— 标签
  - `comments.py` —— 评论
  - `articles/` —— 文章（单独一个包，因为接口最多）：
    - `articles_resource.py` —— 具体接口（列表接口接了 Redis 缓存）
    - `articles_common.py` —— 公共依赖
    - `articles_summary.py` —— AI 摘要接口（`GET` 公开读取 / `POST` 仅作者生成，路径同为 `/api/articles/{slug}/summary`）
  - `hello.py` —— 系统与教学端点：`/`、`/ping`、`/health`（检查数据库等依赖状态）、`/slow`（测耗时中间件）、`/db-test`、`/repo-test`、`/me`、`/required-auth`、`/optional-auth`
  - `items.py` —— Pydantic 教学示例（参数校验、路径/查询参数）
  - `demo/` —— **学习演示接口**，不影响正式接口：
    - `cache.py` —— 缓存读写演示
    - `cache_stats.py` —— 读取 Redis INFO 看缓存统计
    - `session.py` —— 会话管理演示（查看当前会话、踢下线等）
    - `tasks.py` —— `BackgroundTasks` 后台任务演示
    - `websocket.py` —— WebSocket 聊天室演示
  - `api.py` —— 汇总所有路由，统一加前缀 `/api`

- **`dependencies/`** —— **FastAPI 依赖注入**（`Depends` 使用的东西）：
  - `database.py` —— 从连接池拿连接并构造 Repository
  - `authentication.py` —— 解析 JWT 得到当前用户（含会话校验）
  - 其他 `articles.py`、`comments.py`、`profiles.py` —— 各资源公共依赖

- **`errors/`** —— 全局异常处理器：
  - `http_error.py` —— 处理 HTTP 异常
  - `validation_error.py` —— 处理 422 校验错误
  - 统一成 RealWorld 规定的 JSON 格式

### `app/core/` —— 核心配置、基础设施与生命周期

- `config.py` —— 根据环境变量 `APP_ENV` 返回对应的 Settings 实例（用 `@lru_cache` 缓存成单例）
- `settings/` —— 各环境的配置类（继承 pydantic-settings 的 `BaseSettings`，从 `.env` 读配置）：
  - `base.py` —— `BaseAppSettings` 基础配置（`app_env`、`env_file=.env`）
  - `app.py` —— `AppSettings` 通用配置（FastAPI 参数、数据库、Redis、JWT、日志）+ `DevAppSettings` / `ProdAppSettings` / `TestAppSettings` 三个环境子类
- `middleware.py` —— 自定义中间件：`TimingMiddleware`（请求耗时统计、慢请求告警）、`LoggingMiddleware`（请求日志）
- `dependencies.py` —— Redis 相关依赖注入：`RedisDependency`（连接池管理）、`get_redis`、`get_token_storage`
- `cache.py` —— **文章缓存管理器** `ArticleCache`：列表/详情分开建 key 与 TTL，并用「空值哨兵」缓存确定为空的结果，防缓存穿透；另含 AI 摘要缓存 `articles:summary:<id>`（TTL 1 小时，随文章缓存一起失效）
- `cache_decorator.py` —— 通用的 `@cached` 缓存装饰器
- `logging.py` —— loguru 日志配置

### `app/db/` —— 数据访问层

- **`repositories/`** —— **仓库模式**，封装对某个实体的增删改查（`users.py`、`articles.py`、`comments.py`、`profiles.py`、`tags.py`）：
  - `base.py` —— 基类，只持有数据库连接

- **`queries/`** —— 真正的 **SQL 语句**：
  - `queries.py` —— 用 **aiosql** 库从 `sql/` 目录下的 `.sql` 文件自动生成可调用的 Python 函数
  - `sql/` —— SQL 文件（`users.sql`、`articles.sql`、`comments.sql`、`profiles.sql`、`tags.sql`、`favorites.sql`、`followers.sql`）
  - `tables.py` —— 用 pypika 定义表结构

- **`migrations/`** —— Alembic 迁移脚本：
  - `versions/9b2e45876a4f_create_main_tables.py` —— 建表脚本（users、articles、tags、favorites、commentaries 等表）
  - `env.py` / `script.py.mako` —— Alembic 环境配置

- `errors.py` —— 数据层自定义异常（如 `EntityDoesNotExist`）

> 连接池的创建/关闭原先放在 `db/events.py`、`core/events.py`，现已统一收进 `app/main.py` 的 `lifespan`。

### `app/models/` —— 数据模型（两类）

- **`domain/`** —— **领域模型**（内部使用）：
  - `rwmodel.py` —— 基类，定义驼峰别名转换、时间转 ISO 格式
  - `users.py`、`articles.py`、`comments.py`、`profiles.py` —— 各实体领域模型（含业务方法，如 `UserInDB` 的 `change_password`、`check_password`）

- **`schemas/`** —— **请求/响应模型**（对外 DTO）：
  - `rwschema.py` —— 基类，开启 `orm_mode`，用于把领域模型转成响应
  - `jwt.py` —— JWT 载荷模型（含会话 ID `sid`）
  - `users.py`、`articles.py`、`comments.py`、`profiles.py`
  - `summaries.py` —— AI 摘要：LLM 输出的校验模型 `ArticleSummaryContent` + 接口响应 `ArticleSummaryInResponse`
  - 文件名中 `In` 表示入参、`ForResponse`/`InResponse` 表示出参

- `common.py` —— 通用 mixin（id、时间戳）

### `app/services/` —— 业务逻辑层

跨 repository 的纯业务逻辑：

- `articles.py` —— `check_article_exists`、`get_slug_for_article` 等
- `jwt.py` —— 生成/解析 JWT（载荷里带 `sid` 会话标识）
- `security.py` —— 密码哈希（bcrypt）
- `token_storage.py` —— **Redis 会话存储**：白名单策略（JWT 里的 `sid` 必须在 Redis 中存在且一致才算有效）、Token 黑名单、在线用户集合
- `summary.py` —— 摘要生成：`AsyncOpenAI` 调用、总超时（`asyncio.wait_for`）、限流/5xx 重试一次、schema 校验与修复重试
- `authentication.py`、`comments.py` —— 其他业务逻辑

### `app/resources/` —— 资源字符串

- `strings.py` —— 集中存放所有错误提示文案（如"用户不存在"），避免散落在代码里

---

## 三、`tests/` —— 测试

与源码一一对应的单元/集成测试：

| 目录/文件 | 作用 |
|-----------|------|
| `conftest.py` | 测试夹具（fixture），含 asgi-lifespan 管理应用生命周期 |
| `fake_asyncpg_pool.py` | 假的数据库连接池，供测试免真实数据库 |
| `test_api/test_routes/` | 各路由的接口测试（`test_articles`、`test_authentication`、`test_comments`、`test_hello`、`test_profiles`、`test_tags`） |
| `test_schemas/test_rw_model.py` | 模型测试 |
| `test_services/test_jwt.py` | 服务层测试 |

> 运行：`pytest`（或 `bash scripts/test`），配置见 `setup.cfg`。

---

## 四、其他目录

| 目录 | 作用 |
|------|------|
| `demos/` | 学习与演练脚本：`demo_week1_review.py`（第一周综合复习）、`demo_session.py`（Redis 会话演示）、`demo_bench_articles.py`（文章列表并发压测）、`demo_project_health.py`（组件健康检查）、`test_redis.py`、`test_websocket.py` |
| `scripts/` | 便捷命令脚本：`test`（跑 pytest）、`format`（格式化）、`run_dev.bat`（Windows 下带 `--reload` 启动开发服务器） |
| `.github/` | GitHub Actions：`workflows/lint.yml`（代码风格检查）、`workflows/tests.yml`（测试） |
| `.vscode/` | 编辑器配置（调试/解释器设置） |

---

## 五、AI 摘要接口

摘要拆成「读」和「写」两条路径，权限不同：

| 接口 | 方法 | 谁能调 | 语义 |
|------|------|--------|------|
| `/api/articles/{slug}/summary` | `GET` | **所有人（含未登录访客）** | 读取已有摘要；没有则 404 |
| `/api/articles/{slug}/summary` | `POST` | **仅文章作者** | 生成摘要；会调 LLM、会产生费用 |

> 为什么拆开：**看摘要不该有身份门槛，需要保护的是「生成」这个动作**。
> 两个接口共用同一个缓存 key（`articles:summary:<id>`），所以谁读到的一定是同一份。
> `GET` 不写缓存、不调模型，只是一次 Redis 读取。

`POST` 的细节：

| 项 | 说明 |
|----|------|
| 鉴权 | `Authorization: Token <jwt>`；不带 token 返回 401，非作者返回 403 |
| 响应 | `{ "summary": { "summary", "keywords", "difficulty" }, "model", "cached" }` |
| 缓存 | Redis `articles:summary:<article_id>`，TTL 3600 秒；命中时 `cached: true` |
| 并发 | `SET NX EX 60` 锁；拿不到锁返回 409，避免重复调用 LLM |
| 超时 | 总 deadline 由 `LLM_TIMEOUT_SECONDS` 控制（默认 20 秒）；超时返回 504 |
| 失败 | LLM 未配置 / 连接失败 / 限流 / 结构校验失败返回 503 |
| 失效 | 文章更新或删除时，`invalidate_all_articles()` 删除 `articles:*`，摘要缓存一并失效 |

配置项（`.env`，模板见 `.env.example`）：

- `LLM_API_KEY`：LLM 的 key；不配时接口返回 503，其他接口不受影响
- `LLM_BASE_URL`：默认 `https://api.deepseek.com`
- `LLM_MODEL`：默认 `deepseek-flash`
- `LLM_TIMEOUT_SECONDS`：默认 20
- `LLM_MAX_INPUT_CHARS`：默认 6000，正文超过会被截断

成本与评测（2026-XX 实测，10 条自建用例）：

- 单篇平均输入 X token、输出 Y token，按空闲价约 ¥Z/篇；
- 首次延迟 p50 X ms / p95 Y ms；缓存命中 p50 Z ms；
- 成功率 10/10，人工评分 D/20；
- 局限：样本只有 10 条、单人标注、单模型，数字只说明方向，不是 benchmark。

## 总结

这个项目的最大特点是**清晰的分层 + 逐步补上的工程化能力**：

- 路由只负责收发
- 依赖注入负责装配
- 服务层管业务
- 仓库层管数据
- SQL 独立成文件（aiosql）
- 领域模型与出入参模型分离
- 配置按环境拆分（dev / prod / test）
- 生命周期用 `lifespan`，生产环境数据库连不上就 fail fast
- Redis 承担三件事：文章列表/详情缓存 + 会话白名单/黑名单 + AI 摘要缓存
- 日志用 loguru 统一接管，中间件负责耗时统计

它是学习 FastAPI 工程化架构的典型范例。
