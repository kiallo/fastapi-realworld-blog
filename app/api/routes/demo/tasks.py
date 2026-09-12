"""
BackgroundTasks 后台任务演示路由
仅供学习，不影响项目原有接口
"""
from fastapi import APIRouter, BackgroundTasks
from loguru import logger
import asyncio

router = APIRouter()

def send_email_background(email: str, subject: str, body: str):
    """后台发送邮件（模拟）"""
    logger.info(f"📧 开始发送邮件到 {email}...")
    # 模拟耗时操作
    import time
    time.sleep(2)  # 模拟2秒延迟
    logger.info(f"✅ 邮件已发送到 {email}: {subject}")


def log_user_action(user_id: int, action: str):
    """后台记录用户行为"""
    logger.info(f"📝 记录用户行为: user_id={user_id}, action={action}")


@router.post("/register")
async def register_user(
    email: str, 
    password: str,
    background_tasks: BackgroundTasks
):
    """
    用户注册接口
    注册成功后，后台发送欢迎邮件
    """
    # 模拟用户创建
    user_id = 12345
    logger.info(f"👤 用户注册成功: {email}")

    # 添加后台任务
    background_tasks.add_task(
        send_email_background,
        email=email,
        subject="欢迎加入！",
        body="感谢您注册我们的平台"
    )

    # 添加多个后台任务
    background_tasks.add_task(
        log_user_action,
        user_id=user_id,
        action="register"
    )

    return {
        "message": "注册成功",
        "user_id": user_id,
        "note": "欢迎邮件将在后台发送"
    }


@router.get("/test-background")
async def test_background(background_tasks: BackgroundTasks):
    """测试后台任务"""
    
    def slow_task(task_name: str):
        logger.info(f"🔄 开始执行后台任务: {task_name}")
        import time
        time.sleep(3)
        logger.info(f"✅ 后台任务完成: {task_name}")
    
    background_tasks.add_task(slow_task, "清理缓存")
    background_tasks.add_task(slow_task, "更新索引")
    
    return {"message": "请求已返回，后台任务正在执行"}