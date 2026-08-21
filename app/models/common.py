import datetime
from pydantic import BaseModel, Field


def convert_datetime_to_realworld(dt: datetime.datetime) -> str:
    """
    将 datetime 转换为 RealWorld API 规范的 ISO 8601 格式

    RealWorld 规范要求：2024-01-01T00:00:00.000Z
    Python 默认：2024-01-01T00:00:00
    """

    return dt.replace(tzinfo=datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def convert_field_to_camel_case(snake_str: str) -> str:
    """
    将 snake_case 转为 camelCase

    算法：按下划线分割，第一部分保持小写，后续部分首字母大写
    my_database_field → myDatabaseField
    user_id           → userId
    """
    parts = snake_str.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class IDModelMixin(BaseModel):
    """提供 id 字段的 Mixin"""
    id: int = Field(..., description="主键 ID")


class DateTimeModelMixin(BaseModel):
    """
    提供时间戳字段的 Mixin

    注意：不在此处设置 alias，由 RWModel 的 alias_generator 统一生成 camelCase 别名。
    这样类型检查器能正确识别 populate_by_name 的构造函数签名。
    """
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    

    