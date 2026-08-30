class EntityDoesNotExist(Exception):
    """数据实体不存在异常"""
    def __init__(self, message: str = "实体不存在"):
        self.message = message
        super().__init__(self.message)