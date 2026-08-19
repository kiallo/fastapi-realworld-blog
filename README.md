# 项目结构说明

这是一个用 **FastAPI** 实现的 [RealWorld（Conduit 博客后端）](https://github.com/gothinkster/realworld) 示例项目，整体采用清晰的**分层架构**。

---

## 目录总览

```
.
├── .github/            # GitHub 配置（CI、dependabot 等）
├── app/                # 主应用源码
├── postman/            # Postman API 测试集合
├── scripts/            # 便捷命令脚本
├── suggest/            # 教程/说明文件
├── tests/              # 测试代码
├── .dockerignore
├── .env.example        # 环境变量模板
├── .gitignore
├── Dockerfile
├── LICENSE
├── README.rst
├── alembic.ini         # Alembic 数据库迁移配置
├── docker-compose.yml
├── poetry.lock
├── pyproject.toml      # Poetry 依赖管理
└── setup.cfg           # 代码质量工具配置
```

---

## 一、项目根目录文件

| 文件 | 作用 |
|------|------|
| `pyproject.toml` | **Poetry** 依赖管理文件。声明运行时依赖（fastapi、asyncpg、aiosql、passlib、pyjwt、alembic 等）和开发依赖（pytest、black、mypy、wemake-styleguide 等），以及 pytest/isort 配置 |
| `setup.cfg` | **代码质量工具配置**：coverage 覆盖率、mypy 类型检查、flake8/wemake 风格检查规则 |
| `poetry.lock` | Poetry 锁定具体依赖版本的锁文件 |
| `alembic.ini` | **Alembic 数据库迁移**配置，指向迁移脚本目录 `./app/db/migrations` |
| `Dockerfile` | 构建应用镜像 |
| `docker-compose.yml` | 编排两个服务：`app`（应用）+ `db`（PostgreSQL 11.5） |
| `.env.example` | 环境变量模板（SECRET_KEY、DATABASE_URL 等），复制成 `.env` 使用 |
| `.dockerignore` | Docker 构建忽略规则 |
| `.gitignore` | Git 忽略规则 |
| `README.rst` | 项目说明文档 |
| `LICENSE` | MIT 许可证 |

---

## 二、`app/` —— 主应用源码

这是核心，按职责分成 8 个子包，体现清晰的**分层架构**：

```
请求 → routes（路由层）→ dependencies（依赖注入）→ services（业务逻辑）
                                       ↓
                              repositories（仓库层）→ queries（SQL）→ PostgreSQL
                                       ↓
                              models/domain（领域模型）· models/schemas（出入参模型）
```

### `app/main.py` —— 入口

创建 FastAPI 实例 `get_application()`，装配中间件（CORS）、启动/关闭事件、异常处理器，并挂载 API 路由。

### `app/api/` —— API 层（对外接口）

- **`routes/`** —— 路由定义。子文件按资源划分：
  - `authentication.py` —— 注册/登录
  - `users.py` —— 用户
  - `profiles.py` —— 用户关注
  - `tags.py` —— 标签
  - `comments.py` —— 评论
  - `articles/` —— 文章（单独一个包，因为接口最多）：
    - `articles_resource.py` —— 具体接口
    - `articles_common.py` —— 公共依赖
  - `api.py` —— 汇总所有路由并添加前缀

- **`dependencies/`** —— **FastAPI 依赖注入**（`Depends` 使用的东西）：
  - `database.py` —— 从连接池拿连接并构造 Repository
  - `authentication.py` —— 解析 JWT 得到当前用户
  - 其他 `articles.py`、`comments.py`、`profiles.py` —— 各资源公共依赖

- **`errors/`** —— 全局异常处理器：
  - `http_error.py` —— 处理 HTTP 异常
  - `validation_error.py` —— 处理 422 校验错误
  - 统一成 RealWorld 规定的 JSON 格式

### `app/core/` —— 核心配置与生命周期

- `config.py` —— 根据环境变量（dev/prod/test）返回对应的 Settings 实例（用 `@lru_cache` 缓存）
- `settings/` —— 各环境的配置类（继承 pydantic `BaseSettings`，从 `.env` 读配置）：
  - `base.py` —— 基础配置
  - `app.py` —— 应用配置抽象
  - `development.py` / `production.py` / `test.py` —— 各环境具体配置
- `events.py` —— 应用启动/关闭时连接、断开数据库
- `logging.py` —— loguru 日志配置

### `app/db/` —— 数据访问层

- **`repositories/`** —— **仓库模式**，封装对某个实体的增删改查（`users.py`、`articles.py`、`comments.py`、`profiles.py`、`tags.py`）：
  - `base.py` —— 基类，只持有数据库连接

- **`queries/`** —— 真正的 **SQL 语句**：
  - `queries.py` —— 用 **aiosql** 库从 `sql/` 目录下的 `.sql` 文件自动生成可调用的 Python 函数
  - `sql/` —— SQL 文件（`users.sql`、`articles.sql`、`comments.sql`、`profiles.sql`、`tags.sql`）
  - `tables.py` —— 用 pypika 定义表结构

- **`migrations/`** —— Alembic 迁移脚本：
  - `versions/` —— 建表脚本（users、articles、tags、favorites、commentaries 等表）
  - `env.py` / `script.py.mako` —— Alembic 环境配置

- `events.py` —— 用 asyncpg 创建连接池
- `errors.py` —— 数据层自定义异常（如 `EntityDoesNotExist`）

### `app/models/` —— 数据模型（两类）

- **`domain/`** —— **领域模型**（内部使用）：
  - `rwmodel.py` —— 基类，定义驼峰别名转换、时间转 ISO 格式
  - `users.py`、`articles.py`、`comments.py`、`profiles.py` —— 各实体领域模型（含业务方法，如 `UserInDB` 的 `change_password`、`check_password`）

- **`schemas/`** —— **请求/响应模型**（对外 DTO）：
  - `rwschema.py` —— 基类，开启 `orm_mode`，用于把领域模型转成响应
  - 文件名中 `In` 表示入参、`ForResponse`/`InResponse` 表示出参

- `common.py` —— 通用 mixin（id、时间戳）

### `app/services/` —— 业务逻辑层

跨 repository 的纯业务逻辑：

- `articles.py` —— `check_article_exists`、`get_slug_for_article` 等
- `jwt.py` —— 生成/解析 JWT
- `security.py` —— 密码哈希（bcrypt）
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
| `test_api/test_routes/` | 各路由的接口测试（articles、authentication、login、registration 等） |
| `test_api/test_errors/` | 错误处理测试 |
| `test_db/` | 数据层测试（查询表结构） |
| `test_schemas/` | 模型测试 |
| `test_services/` | 服务层测试 |

> 注意：`pyproject.toml` 里配置了 `--cov-fail-under=100`，即要求 **100% 测试覆盖率**。

---

## 四、其他目录

| 目录 | 作用 |
|------|------|
| `scripts/` | 便捷命令脚本：`test`、`lint`、`format`、`test-cov-html`，对 pytest/flake8/black 的简单封装 |
| `postman/` | Postman 的 API 测试集合（`Conduit.postman_collection.json`）和自动化测试脚本，方便用 Postman 手动调接口 |
| `.github/` | GitHub 相关配置：`workflows/` 是 CI（测试、风格检查、部署等），`dependabot.yml` 自动升级依赖，`assets/` 是 logo |

---

## 总结

这个项目的最大特点是**清晰的分层**：

- 路由只负责收发
- 依赖注入负责装配
- 服务层管业务
- 仓库层管数据
- SQL 独立成文件（aiosql）
- 领域模型与出入参模型分离
- 配置按环境拆分

它是学习 FastAPI 工程化架构的典型范例。