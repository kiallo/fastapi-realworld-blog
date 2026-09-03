from fastapi import APIRouter
from app.api.routes import hello, users, items, authentication
from app.api.routes.articles.articles_resource import router as articles_router

router = APIRouter(prefix="/api")

# 挂载各模块路由
router.include_router(hello.router, tags=["system"])
router.include_router(users.router)
router.include_router(items.router)
router.include_router(authentication.router) 
router.include_router(articles_router)