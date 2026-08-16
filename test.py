from loguru import logger

child_logger = logger.bind(user_id=123, request_id="abc")
child_logger.info("用户登录")  # 自动附加 user_id 和 request_id