from fastapi import FastAPI
from typing import Optional

app = FastAPI(
    title="RealWorld Blog API",
    description="一个符合 RealWorld 规范的博客 API",
    version="0.1.0",
)


@app.get("/")
async def root():
    """根路径 — 健康检查"""
    return {"message": "RealWorld Blog API 运行中", "status": "ok"}


# ===== 路径参数 =====

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """路径参数：{user_id} 自动转换为 int"""
    return {"user_id": user_id, "type": type(user_id).__name__}


# ===== 查询参数 =====

@app.get("/search")
async def search(
    q: str,
    page: int = 1,
    limit: int = 10,
):
    """查询参数：?q=关键词&page=1&limit=10"""
    return {
        "query": q,
        "page": page,
        "limit": limit,
        "results": f"搜索「{q}」第 {page} 页，每页 {limit} 条",
    }


# ===== 请求体（POST）=====

from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    price: float
    description: Optional[str] = None


@app.post("/items", status_code=201)
async def create_item(item: ItemCreate):
    """请求体自动校验：name 和 price 必填，description 可选"""
    return {
        "message": "商品创建成功",
        "item": item.model_dump(),
    }


# ===== response_model 过滤输出 =====

class ItemResponse(BaseModel):
    name: str
    price: float
    # 注意：没有 description 字段！


@app.post("/items/safe", response_model=ItemResponse, status_code=201)
async def create_item_safe(item: ItemCreate):
    """response_model 会自动过滤掉 description，只返回 name 和 price"""
    return item  # FastAPI 自动转换为 ItemResponse