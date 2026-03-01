"""ReAct Chat Loop tests — early exit, re-search, max turns."""
from unittest.mock import patch, MagicMock

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "web_app"))


class TestReActLoop:
    def test_early_exit_on_document_qa(self):
        """Turn 1 returns document_qa → immediate return, no loop."""
        from services.web_app.react_chat import react_chat_loop

        with patch("services.web_app.react_chat._single_turn") as mock_turn:
            mock_turn.return_value = ("document_qa", "답변입니다.", [{"page": 1, "text": "ref"}])

            tool, answer, refs = react_chat_loop(
                api_key="test",
                message="자격요건 알려줘",
                company_context_text="회사 정보",
                rfx_context_text="RFx 내용",
                session=MagicMock(),
            )
            assert tool == "document_qa"
            assert answer == "답변입니다."
            assert mock_turn.call_count == 1

    def test_early_exit_on_general_response(self):
        """Turn 1 returns general_response → immediate return."""
        from services.web_app.react_chat import react_chat_loop

        with patch("services.web_app.react_chat._single_turn") as mock_turn:
            mock_turn.return_value = ("general_response", "안녕하세요!", [])

            tool, answer, refs = react_chat_loop(
                api_key="test",
                message="안녕",
                company_context_text="",
                rfx_context_text="",
                session=MagicMock(),
            )
            assert tool == "general_response"
            assert mock_turn.call_count == 1

    def test_react_loop_need_more_context_then_answer(self):
        """Turn 1: need_more_context → Turn 2: document_qa answer."""
        from services.web_app.react_chat import react_chat_loop

        with patch("services.web_app.react_chat._single_turn") as mock_turn, \
             patch("services.web_app.react_chat._rebuild_context") as mock_rebuild:
            mock_turn.side_effect = [
                ("need_more_context", "자격요건 상세", [{"reason": "불충분", "scope": "rfx"}]),
                ("document_qa", "상세 답변입니다.", [{"page": 5, "text": "상세 ref"}]),
            ]
            mock_rebuild.return_value = ("새 회사ctx", "새 RFx ctx")

            tool, answer, refs = react_chat_loop(
                api_key="test",
                message="복합 질문",
                company_context_text="",
                rfx_context_text="",
                session=MagicMock(),
            )
            assert tool == "document_qa"
            assert answer == "상세 답변입니다."
            assert mock_turn.call_count == 2
            mock_rebuild.assert_called_once_with(session=mock_turn.call_args_list[0][1]["session"],
                                                  query="자격요건 상세", scope="rfx")

    def test_max_3_turns_forced_exit(self):
        """After 2 need_more_context, force final answer on turn 3."""
        from services.web_app.react_chat import react_chat_loop

        with patch("services.web_app.react_chat._single_turn") as mock_turn, \
             patch("services.web_app.react_chat._rebuild_context") as mock_rebuild, \
             patch("services.web_app.react_chat._force_final_answer") as mock_force:
            mock_turn.side_effect = [
                ("need_more_context", "q1", [{"reason": "r1", "scope": "rfx"}]),
                ("need_more_context", "q2", [{"reason": "r2", "scope": "both"}]),
            ]
            mock_rebuild.return_value = ("", "")
            mock_force.return_value = ("document_qa", "강제 답변", [])

            tool, answer, refs = react_chat_loop(
                api_key="test",
                message="매우 복합적 질문",
                company_context_text="",
                rfx_context_text="",
                session=MagicMock(),
                max_turns=3,
            )
            assert answer == "강제 답변"
            assert mock_force.call_count == 1
            # 2 regular turns + 1 forced = total
            assert mock_turn.call_count == 2

    def test_rebuild_context_company_only(self):
        """_rebuild_context with scope=company only searches company engine."""
        from services.web_app.react_chat import _rebuild_context

        session = MagicMock()
        session.rag_engine.search.return_value = [
            ("company doc text", {"source_file": "company.pdf", "page_number": 3}),
        ]
        session.rfx_rag_engine.search.return_value = []

        company, rfx = _rebuild_context(session=session, query="test query", scope="company")
        assert "company doc text" in company
        assert rfx == ""
        session.rag_engine.search.assert_called_once_with("test query", top_k=12)
        session.rfx_rag_engine.search.assert_not_called()

    def test_rebuild_context_error_handling(self):
        """_rebuild_context handles search errors gracefully."""
        from services.web_app.react_chat import _rebuild_context

        session = MagicMock()
        session.rag_engine.search.side_effect = RuntimeError("DB error")

        company, rfx = _rebuild_context(session=session, query="test", scope="both")
        assert company == ""
        assert rfx == ""


class TestParseNeedMoreContext:
    def test_parse_need_more_context_tool(self):
        """parse_tool_call_result handles need_more_context correctly."""
        from chat_tools import parse_tool_call_result
        import json

        message = MagicMock()
        tool_call = MagicMock()
        tool_call.function.name = "need_more_context"
        tool_call.function.arguments = json.dumps({
            "reason": "자격요건 정보 부족",
            "suggested_query": "자격요건 상세 조건",
            "search_scope": "rfx",
        })
        message.tool_calls = [tool_call]

        tool_name, answer, refs = parse_tool_call_result(message)
        assert tool_name == "need_more_context"
        assert answer == "자격요건 상세 조건"  # suggested_query
        assert refs[0]["reason"] == "자격요건 정보 부족"
        assert refs[0]["scope"] == "rfx"
