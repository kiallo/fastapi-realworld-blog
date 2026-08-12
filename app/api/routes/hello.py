from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    """根路径 - 健康检查"""
    return {"message": "RealWorld Blog API 运行中", "status": "ok"}


@router.get("/ping")
async def ping():
    """Ping 端点 — 负载均衡器常用"""
    return {"ping": "pong"}