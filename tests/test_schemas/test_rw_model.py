"""RWModel 序列化测试"""
import pytest
import datetime
from app.models.domain.rwmodel import RWModel
from app.models.common import convert_field_to_camel_case, convert_datetime_to_realworld


class SampleModel(RWModel):
    """测试用模型"""
    user_name: str
    is_active: bool = True
    created_at: datetime.datetime = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)


def test_camel_case_alias_generation():
    """snake_case 字段自动生成 camelCase 别名"""
    model = SampleModel(user_name="test", created_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc))
    # 通过别名访问
    assert model.model_dump(by_alias=True)["userName"] == "test"
    assert model.model_dump(by_alias=True)["isActive"] is True


def test_camel_case_helper():
    """convert_field_to_camel_case — 基本转换"""
    assert convert_field_to_camel_case("user_name") == "userName"
    assert convert_field_to_camel_case("is_active") == "isActive"
    assert convert_field_to_camel_case("created_at") == "createdAt"
    assert convert_field_to_camel_case("id") == "id"


def test_datetime_serialization():
    """datetime 序列化为 RealWorld 规范格式"""
    dt = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)
    result = convert_datetime_to_realworld(dt)
    assert result == "2024-01-15T10:30:00Z"


def test_model_dump_by_alias():
    """model_dump(by_alias=True) 输出 camelCase 键"""
    model = SampleModel(
        user_name="alice",
        is_active=False,
        created_at=datetime.datetime(2024, 6, 1, tzinfo=datetime.timezone.utc),
    )
    data = model.model_dump(by_alias=True)
    assert "userName" in data
    assert "isActive" in data
    assert "createdAt" in data
    assert "user_name" not in data


def test_model_dump_by_field_name():
    """model_dump(by_alias=False) 输出 snake_case 键"""
    model = SampleModel(
        user_name="bob",
        created_at=datetime.datetime(2024, 6, 1, tzinfo=datetime.timezone.utc),
    )
    data = model.model_dump(by_alias=False)
    assert "user_name" in data
    assert "is_active" in data
    assert "created_at" in data


def test_populate_by_name():
    """可以通过 snake_case 或 camelCase 创建模型"""
    # snake_case
    model1 = SampleModel(user_name="a", created_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc))
    assert model1.user_name == "a"

    # camelCase（需要 populate_by_name=True）
    model2 = SampleModel.model_validate({"userName": "b", "createdAt": "2024-01-01T00:00:00Z"})
    assert model2.user_name == "b"
