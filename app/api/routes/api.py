from fastapi import APIRouter
from app.api.routes import hello, users, items, authentication
from app.api.routes.articles.articles_resource import router as articles_router
from app.api.routes.articles.articles_common import router as articles_common_router
from app.api.routes.tags import router as tags_router
from app.api.routes.profiles import router as profiles_router
from app.api.routes.comments import router as comments_router
from app.api.routes.demo_cache import router as demo_cache_router
from app.api.routes.demo_tasks import router as demo_tasks_router
from app.api.routes.demo_websocket import router as demo_websocket_router

router = APIRouter(prefix="/api")

# 挂载各模块路由
router.include_router(hello.router, tags=["system"])
router.include_router(users.router)
router.include_router(items.router)
router.include_router(authentication.router) 
router.include_router(articles_router, tags=["articles"], prefix="/articles")
router.include_router(articles_common_router, prefix="/articles")
router.include_router(tags_router)
router.include_router(profiles_router, tags=["profiles"], prefix="/profiles")
router.include_router(comments_router, tags=["comments"], prefix="/articles/{slug}/comments")
router.include_router(demo_cache_router, tags=["demo"])
router.include_router(demo_tasks_router, tags=["demo"], prefix="/tasks")  
router.include_router(demo_websocket_router, tags=["demo"], prefix="/ws")    