from typing import Optional
from fastapi import APIRouter, Query, Path
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/items",
    tags=["items"],
)


# ===== Pydantic 模型定义 =====
class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="商品名称")
    price: float = Field(..., gt=0, description="价格，必须大于 0")
    description: Optional[str] = Field(None, max_length=500, description="商品描述")

class ItemResponse(BaseModel):
    name: str
    price: float


# ===== 端点 =====

@router.get("")
async def list_items(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, min_length=1, description="搜索关键词"),
):
    """商品列表 — 支持分页和搜索"""
    return {
        "page": page,
        "limit": limit,
        "keyword": keyword,
        "results": [],
    }


@router.get("/{item_id}")
async def get_item(
    item_id: int = Path(..., ge=1, description="商品 ID"),
):
    """获取单个商品"""
    return {"item_id": item_id}


@router.post("", status_code=201)
async def create_item(item: ItemCreate):
    """创建商品"""
    return {"message": "创建成功", "item": item.model_dump()}


@router.post("/safe", response_model=ItemResponse, status_code=201)
async def create_item_safe(item: ItemCreate):
    """创建商品（安全响应）— 不暴露 description"""
    return item  # FastAPI 自动过滤为 ItemResponse