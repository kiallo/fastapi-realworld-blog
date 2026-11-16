"""摘要服务的容错逻辑：JSON 抽取、重试、超时、连接失败。

全部对纯函数和服务类断言：不走 HTTP、不连数据库、不调真实 LLM、不产生费用。
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.services.summary import (
    SummaryError,
    SummaryService,
    SummaryTimeoutError,
    extract_json,
)

VALID_JSON = (
    '{"summary": "这是一段足够长的摘要内容，用于通过 pydantic 校验。",'
    ' "keywords": ["python", "fastapi"], "difficulty": "beginner"}'
)


def _response(content, prompt=10, completion=5):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage = MagicMock(prompt_tokens=prompt, completion_tokens=completion)
    return resp


def _http_error(status_code):
    return APIStatusError(
        "llm error",
        response=httpx.Response(status_code, request=httpx.Request("POST", "http://llm")),
        body=None,
    )


def _service(client, timeout=5.0, max_chars=100):
    return SummaryService(
        client=client, model="test-model", timeout=timeout, max_input_chars=max_chars
    )


class TestExtractJson:
    def test_plain_json(self):
        assert extract_json(VALID_JSON) == VALID_JSON

    def test_json_inside_code_fence(self):
        """模型很爱把 JSON 包在 ```json 围栏里"""
        assert extract_json(f"```json\n{VALID_JSON}\n```") == VALID_JSON

    def test_json_with_surrounding_text(self):
        """前后有多余解释也要能抠出来"""
        assert extract_json(f"好的，结果如下：\n{VALID_JSON}\n希望有帮助。") == VALID_JSON

    def test_missing_braces_raises(self):
        with pytest.raises(ValueError, match="找不到 JSON"):
            extract_json("完全没有 JSON")

    def test_truncated_json_raises(self):
        """只有左括号 = 模型输出被截断，必须报错而不是返回半截"""
        with pytest.raises(ValueError, match="找不到 JSON"):
            extract_json('{"summary": "只有开头')


class TestGenerate:
    async def test_success_returns_content_and_usage(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_response(VALID_JSON))

        content, usage = await _service(client).generate(title="标题", body="正文")

        assert content.difficulty == "beginner"
        assert len(content.keywords) == 2
        assert usage == {"input_tokens": 10, "output_tokens": 5}

    async def test_body_is_truncated_to_max_chars(self):
        """控制成本：长文不能整篇塞给模型"""
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_response(VALID_JSON))

        await _service(client, max_chars=10).generate(title="t", body="x" * 1000)

        sent = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert sent.count("x") == 10

    async def test_usage_none_yields_zero(self):
        """模型不返回 usage 时不能崩，归零即可"""
        resp = _response(VALID_JSON)
        resp.usage = None
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=resp)

        _, usage = await _service(client).generate(title="t", body="b")

        assert usage == {"input_tokens": 0, "output_tokens": 0}

    async def test_invalid_output_then_fixed_on_retry(self):
        """第一次返回非 JSON → 追加纠错消息重试 → 第二次成功"""
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=[_response("我不是 JSON"), _response(VALID_JSON)]
        )

        content, _ = await _service(client).generate(title="t", body="b")

        assert content.difficulty == "beginner"
        assert client.chat.completions.create.await_count == 2

    async def test_invalid_twice_raises_summary_error(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_response("永远不是 JSON"))

        with pytest.raises(SummaryError, match="结构化输出失败"):
            await _service(client).generate(title="t", body="b")

    async def test_api_timeout_raises_timeout_error(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=MagicMock()))

        with pytest.raises(SummaryTimeoutError):
            await _service(client).generate(title="t", body="b")

    async def test_connection_error_raises_summary_error(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        with pytest.raises(SummaryError, match="连接失败"):
            await _service(client).generate(title="t", body="b")

    async def test_500_retries_once_then_fails(self):
        """5xx 首次重试，第二次仍 5xx 才抛"""
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=_http_error(500))

        with pytest.raises(SummaryError, match="调用失败"):
            await _service(client).generate(title="t", body="b")

        assert client.chat.completions.create.await_count == 2

    async def test_4xx_does_not_retry(self):
        """4xx 是请求本身有问题，重试没用，一次就抛"""
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=_http_error(400))

        with pytest.raises(SummaryError, match="调用失败"):
            await _service(client).generate(title="t", body="b")

        assert client.chat.completions.create.await_count == 1
