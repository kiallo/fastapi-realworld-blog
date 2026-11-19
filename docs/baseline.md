# 性能基线（阶段 0）

- 采集时间：2026-11-18 :\_\_
- 提交：`git rev-parse --short HEAD` 的输出
- 分支：feature/observability

## 1. 环境

| 项         | 值                                                                             |
| ---------- | ------------------------------------------------------------------------------ |
| CPU        | AMD Ryzen 7 8845H w/ Radeon 780M Graphics / 8 核 16 线程                       |
| 内存       | 13.8 GB                                                                        |
| 磁盘       | SSD / Micron MTFDKCD1T0TFK                                                     |
| OS         | Windows 11 <版本>                                                              |
| Python     | 3.14.3（Poetry 环境）                                                          |
| 启动方式   | `poetry run uvicorn app.main:app --host 127.0.0.1 --port 18000`（无 --reload） |
| 应用进程数 | 1                                                                              |

## 2. 数据量

| 表        | 行数 |
| --------- | ---- |
| users     | 32   |
| articles  | 426  |
| comments  | 3    |
| favorites | 3    |

## 3. 三条路径的含义

| 路径                  | 代码位置                                                   | 实际打到哪                                                |
| --------------------- | ---------------------------------------------------------- | --------------------------------------------------------- |
| list_anon（匿名列表） | `app/api/routes/articles/articles_resource.py` 第 74–89 行 | 先查 Redis，命中就直接返回                                |
| list_auth（登录列表） | 同上，但 `use_cache=False`（第 72 行）                     | 每次 5 条 SQL（主查询 + 作者 + 标签 + 收藏数 + 是否收藏） |
| detail（详情）        | `app/api/dependencies/articles.py:46`                      | 每次 4～5 条 SQL，**没有缓存**                            |

## 4. 结果

| 负载      | VUs        | QPS   | P50(ms) | P95(ms) | P99(ms) | 错误率 |
| --------- | ---------- | ----- | ------- | ------- | ------- | ------ |
| list_anon | 20（首轮） | 80.4  | 7.5     | 15.1    | 30.5    | 0.00%  |
| list_anon | 50         | 203.1 | 8.0     | 20.2    | 34.6    | 0.00%  |
| list_anon | 100        | 371.5 | 26.3    | 60.4    | 80.0    | 0.00%  |
| list_auth | 50         | 192.8 | 18.0    | 39.0    | 64.9    | 0.00%  |
| detail    | 20         | 81.1  | 9.8     | 16.1    | 27.7    | 0.00%  |
| detail    | 50         | 199.2 | 9.4     | 18.2    | 34.4    | 0.00%  |
| detail    | 100        | 376.0 | 19.1    | 52.0    | 75.0    | 0.00%  |

## 5. 波动检查

同一配置连跑 3 次，QPS 极差：1.45%
（> 15% 说明环境不稳，先解决环境，不要开始优化）

## 6. 一句话结论

当前单实例、426 篇文章、50 并发下，最慢的是 list_auth（登录列表，不走缓存），
P95 = 39.0 ms，瓶颈初步怀疑在 PostgreSQL（每次 5 条 SQL）叠加鉴权与 20 行序列化，待第 7 部分验证。

## 7. 局限

- 本机 Windows + Docker 里的 PostgreSQL，与 Linux 生产环境不可直接比较；
- 单进程单 worker，未开多核；
- 数据是合成数据，正文长度固定，真实数据的正文分布不同。

## 备份命令

```powershell
① 在容器里生成备份（-Fc = 二进制自定义格式，pg_restore 专用）
docker compose exec -T db pg_dump -U postgres -Fc -f /tmp/before-seed.dump realworld

② 搬出来（这一步是字节级复制，不经过 PowerShell 的编码器）
docker compose cp db:/tmp/before-seed.dump ./realworld-before-seed.dump

③ 验：大小对得上，且头几个字节是 "PGDMP"
(Get-Item realworld-before-seed.dump).Length
(Get-Content realworld-before-seed.dump -Encoding Byte -TotalCount 5 | ForEach-Object { [char]$_ }) -join ''
```

## 恢复方式

```powershell
docker compose cp ./realworld-before-seed.dump db:/tmp/restore.dump

docker compose exec -T db pg_restore -U postgres -d realworld --clean --if-exists /tmp/restore.dump
```
