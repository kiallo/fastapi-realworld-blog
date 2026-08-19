import datetime
from pydantic import BaseModel, ConfigDict
from app.models.common import convert_datetime_to_realworld, convert_field_to_camel_case


class RWModel(BaseModel):
    """
    Domain 层基类 — 纯业务模型

    职责：
    1. 自动 snake_case → camelCase 别名（适应 JSON 驼峰命名约定）
    2. 自定义 datetime 序列化为 RealWorld 规范格式
    3. 允许通过字段名或别名赋值
    """

    model_config = ConfigDict(
        # 允许通过 Python 字段名（snake_case）或 JSON 别名（camelCase）赋值
        populate_by_name=True,

        # 自定义 JSON 序列化规则
        json_encoders={
            datetime.datetime: convert_datetime_to_realworld,
        },

        # 自动为所有字段生成 camelCase 别名
        alias_generator=convert_field_to_camel_case
    )