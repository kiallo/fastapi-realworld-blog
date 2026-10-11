FROM python:3.12-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN pip install --no-cache-dir poetry

# 复制依赖文件
COPY pyproject.toml poetry.lock ./

# 安装项目依赖（不安装 dev 依赖）
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root --without dev

# 复制项目代码
COPY . .

# 暴露端口
# 注意：容器内部用 18000 是为了和宿主机保持一致。
# 容器是独立的 Linux 网络命名空间，本身不存在 Windows 端口保留的问题，
# 真正会被 Windows「征用」的是 docker-compose 里映射到宿主机的那个端口。
EXPOSE 18000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000"]