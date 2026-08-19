from pydantic import ConfigDict
from app.models.domain.rwmodel import RWModel


class RWSchema(RWModel):
    """
    Schema 层基类 — 面向 HTTP 的请求/响应模型

    与 RWModel 的区别：开启 from_attributes（原 orm_mode），
    支持从 ORM 对象直接创建模型
    """

    model_config = ConfigDict(
        from_attributes=True,  # Pydantic v2 的 orm_mode 替代
        populate_by_name=True,
        alias_generator=RWModel.model_config.get("alias_generator"),
    )