"""chat_tools.py 단위 테스트."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat_tools import CHAT_TOOLS, parse_tool_call_result


def test_four_tools_defined():
    assert len(CHAT_TOOLS) == 4
    names = {t["function"]["name"] for t in CHAT_TOOLS}
    assert names == {"document_qa", "general_response", "bid_search", "bid_analyze"}


def test_all_tools_have_answer_param():
    for tool in CHAT_TOOLS:
        props = tool["function"]["parameters"]["properties"]
        assert "answer" in props


def test_parse_document_qa():
    msg = MagicMock()
    call = MagicMock()
    call.function.name = "document_qa"
    call.function.arguments = json.dumps({
        "answer": "답변",
        "references": [
            {"page": 3, "text": "원문"},
            {"page": 0, "text": "무효"},
        ],
    })
    msg.tool_calls = [call]
    name, answer, refs = parse_tool_call_result(msg)
    assert name == "document_qa"
    assert answer == "답변"
    assert len(refs) == 1 and refs[0]["page"] == 3


def test_parse_general_response():
    msg = MagicMock()
    call = MagicMock()
    call.function.name = "general_response"
    call.function.arguments = json.dumps({"answer": "안녕하세요!"})
    msg.tool_calls = [call]
    name, answer, refs = parse_tool_call_result(msg)
    assert name == "general_response" and refs == []


def test_parse_no_tool_call_fallback():
    msg = MagicMock()
    msg.tool_calls = None
    msg.content = "직접 응답"
    name, answer, refs = parse_tool_call_result(msg)
    assert name == "general_response" and answer == "직접 응답"
