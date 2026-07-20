"""目的：验证 LLM JSON 提取的容错行为。

定义：llm_client._extract_json 的窄范围单元测试。

范围包括：
- markdown 代码块、尾随解释文本、字符串内花括号和空响应解析。

范围不包括：
- 不调用真实 LLM，不验证 OpenAI SDK 网络行为。

使用与修改规则：
- 仅覆盖稳定解析契约；新增解析策略时补充等价输入样例。
"""

import pytest

from app.llm_client import LLMEnhancementError, _extract_json


def test_extract_json_from_markdown_code_block() -> None:
    content = """```json
{"answer": "ok", "items": [1, 2]}
```"""

    assert _extract_json(content) == {"answer": "ok", "items": [1, 2]}


def test_extract_json_with_trailing_explanation_text() -> None:
    content = '{"answer": "ok"}\n\n以上是分析结果。'

    assert _extract_json(content) == {"answer": "ok"}


def test_extract_json_ignores_braces_inside_strings() -> None:
    content = '前缀说明 {"pattern": "对象 {A} 到 {B}", "escaped": "quote \\" } still string"} 后缀'

    assert _extract_json(content) == {
        "pattern": "对象 {A} 到 {B}",
        "escaped": 'quote " } still string',
    }


def test_extract_json_empty_response_raises() -> None:
    with pytest.raises(LLMEnhancementError, match="did not contain a JSON object"):
        _extract_json("")
