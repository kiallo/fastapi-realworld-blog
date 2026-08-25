import pathlib
import aiosql


# SQL 文件所在目录
_sql_dir = pathlib.Path(__file__).parent / "sql"

# 加载所有 .sql 文件中的查询（显式指定 UTF-8，避免 Windows GBK 编码问题）
queries = aiosql.from_path(_sql_dir, driver_adapter="asyncpg", encoding="utf-8")