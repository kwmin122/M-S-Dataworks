"""
Phase 0 baseline runner.

Purpose:
1) Validate end-to-end pipeline with dummy/real RFx files.
2) Measure baseline metrics before weighted scoring upgrade.
3) Capture top failure patterns for Andrew Ng-style error analysis.

Usage:
    python scripts/phase0_baseline.py \
      --company "/abs/path/company.pdf" \
      --rfx "/abs/path/rfx.pdf" \
      --out "reports/phase0_baseline.json"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from document_parser import DocumentParser
from engine import RAGEngine
from matcher import QualificationMatcher
from pdf_highlighter import HighlightManager
from response_parser import parse_chat_response
from rfx_analyzer import RFxAnalyzer, RFxParseError


@dataclass
class BaselineMetrics:
    extraction_success: int = 0
    extraction_attempts: int = 0
    matching_success: int = 0
    matching_attempts: int = 0
    llm_format_success: int = 0
    llm_format_attempts: int = 0
    highlight_success: int = 0
    highlight_attempts: int = 0

    def to_rates(self) -> dict[str, Optional[float]]:
        def rate(ok: int, total: int) -> Optional[float]:
            if total <= 0:
                return None
            return round(ok / total, 4)

        return {
            "extraction_success_rate": rate(self.extraction_success, self.extraction_attempts),
            "matching_completion_rate": rate(self.matching_success, self.matching_attempts),
            "llm_format_compliance_rate": rate(self.llm_format_success, self.llm_format_attempts),
            "highlight_success_rate": rate(self.highlight_success, self.highlight_attempts),
        }


class Phase0BaselineRunner:
    """Run Phase 0 metrics on one company PDF + one RFx PDF."""

    def __init__(self, company_path: str, rfx_path: str, model: str):
        self.company_path = Path(company_path)
        self.rfx_path = Path(rfx_path)
        self.model = model
        self.metrics = BaselineMetrics()
        self.failures: Counter[str] = Counter()
        self.failure_details: Counter[str] = Counter()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rfx_phase0_"))
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.company_rag = RAGEngine(
            persist_directory=str(self.temp_dir / "vectordb"),
            collection_name="company_phase0",
        )
        self.rfx_rag = RAGEngine(
            persist_directory=str(self.temp_dir / "vectordb"),
            collection_name="rfx_phase0",
        )
        self.rfx_analysis = None
        self.matching_result = None

    def cleanup(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run(self) -> dict[str, Any]:
        # STEP 1: input validation
        self._validate_inputs()

        # STEP 2: load company KB
        self._load_company_kb()

        # STEP 3: analyze RFx
        self._analyze_rfx()

        # STEP 4: build RFx KB with page metadata
        self._build_rfx_kb()

        # STEP 5: qualification matching
        self._run_matching()

        # STEP 6: chat-format/highlight compliance (if API available)
        self._run_llm_format_and_highlight_tests()

        # STEP 7: aggregate report
        top_failures = [{"type": k, "count": v} for k, v in self.failures.most_common(3)]
        top_failure_details = [{"detail": k, "count": v} for k, v in self.failure_details.most_common(5)]
        return {
            "inputs": {
                "company_file": str(self.company_path),
                "rfx_file": str(self.rfx_path),
                "model": self.model,
                "api_key_present": bool(self.api_key),
            },
            "metrics": self.metrics.to_rates(),
            "counts": {
                "requirements_extracted": len(self.rfx_analysis.requirements) if self.rfx_analysis else 0,
                "matching_items": len(self.matching_result.matches) if self.matching_result else 0,
            },
            "top_failures": top_failures,
            "top_failure_details": top_failure_details,
            "notes": self._build_notes(top_failures),
        }

    def _validate_inputs(self) -> None:
        if not self.company_path.exists():
            raise FileNotFoundError(f"Company file not found: {self.company_path}")
        if not self.rfx_path.exists():
            raise FileNotFoundError(f"RFx file not found: {self.rfx_path}")

    def _load_company_kb(self) -> None:
        try:
            self.company_rag.clear_collection()
            self.company_rag.add_document(str(self.company_path))
        except Exception:
            self.failures["company_kb_load_failed"] += 1
            raise

    def _analyze_rfx(self) -> None:
        self.metrics.extraction_attempts += 1
        if not self.api_key:
            self.failures["missing_openai_api_key"] += 1
            return

        try:
            analyzer = RFxAnalyzer(api_key=self.api_key, model=self.model)
            self.rfx_analysis = analyzer.analyze(str(self.rfx_path))
            if self.rfx_analysis.requirements:
                self.metrics.extraction_success += 1
            else:
                self.failures["requirements_empty"] += 1
        except RFxParseError:
            self.failures["rfx_parse_error"] += 1
            self.failure_details["rfx_parse_error:RFxParseError"] += 1
        except Exception as exc:
            self.failures["rfx_analysis_failed"] += 1
            detail = f"rfx_analysis_failed:{type(exc).__name__}:{str(exc)[:160]}"
            self.failure_details[detail] += 1

    def _build_rfx_kb(self) -> None:
        self.rfx_rag.clear_collection()
        try:
            parsed = DocumentParser().parse(str(self.rfx_path))
            if parsed.pages:
                for page_idx, page_text in enumerate(parsed.pages, start=1):
                    self.rfx_rag.add_text_directly(
                        page_text,
                        source_name=f"RFx_{self.rfx_path.name}_p{page_idx}",
                        base_metadata={"page_number": page_idx, "type": "rfx_text"},
                    )
            elif parsed.text:
                self.rfx_rag.add_text_directly(
                    parsed.text,
                    source_name=f"RFx_{self.rfx_path.name}",
                    base_metadata={"page_number": -1, "type": "rfx_text"},
                )
        except Exception:
            self.failures["rfx_kb_load_failed"] += 1
            raise

    def _run_matching(self) -> None:
        self.metrics.matching_attempts += 1
        if not self.api_key:
            self.failures["missing_openai_api_key"] += 1
            return
        if not self.rfx_analysis:
            self.failures["missing_rfx_analysis"] += 1
            return

        try:
            matcher = QualificationMatcher(
                rag_engine=self.company_rag,
                api_key=self.api_key,
                model=self.model,
            )
            self.matching_result = matcher.match(self.rfx_analysis)
            if self.matching_result.matches:
                self.metrics.matching_success += 1
            else:
                self.failures["matching_empty"] += 1
        except Exception:
            self.failures["matching_failed"] += 1

    def _run_llm_format_and_highlight_tests(self) -> None:
        if not self.api_key:
            return

        try:
            from openai import OpenAI
        except Exception:
            self.failures["openai_import_failed"] += 1
            return

        questions = [
            "이 공고의 핵심 자격요건 3개를 요약해줘.",
            "우리 회사가 즉시 보완해야 할 미충족 항목은?",
            "참조 페이지와 함께 준비 체크리스트를 줘.",
        ]
        system_prompt = """당신은 입찰 전문 AI입니다.
반드시 JSON 객체만 반환하세요:
{
  "answer": "한국어 답변",
  "references": [{"page": 1, "text": "근거 문구"}]
}
중요 규칙:
1) references.text는 RFx 원문에서 그대로 복사한 연속 구간만 사용하세요(의역 금지).
2) references.text는 가능한 12~80자 핵심 구절로 반환하세요.
3) references는 최대 5개입니다."""

        client = OpenAI(api_key=self.api_key)
        pdf_bytes = self.rfx_path.read_bytes()
        hm = HighlightManager(pdf_bytes=pdf_bytes)
        try:
            for question in questions:
                self.metrics.llm_format_attempts += 1
                self.metrics.highlight_attempts += 1

                company_ctx = self._build_context(self.company_rag, question, "회사")
                rfx_ctx = self._build_context(self.rfx_rag, question, "RFx")
                user_prompt = f"질문: {question}\n\n{company_ctx}\n\n{rfx_ctx}\n\nJSON으로만 답변하세요."

                try:
                    response = client.chat.completions.create(
                        model=self.model,
                        temperature=0.2,
                        max_tokens=1000,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    )
                    raw_text = (response.choices[0].message.content or "").strip()
                except Exception as exc:
                    self.failures["llm_call_failed"] += 1
                    detail = f"llm_call_failed:{type(exc).__name__}:{str(exc)[:160]}"
                    self.failure_details[detail] += 1
                    continue

                if self._is_strict_json_format(raw_text):
                    self.metrics.llm_format_success += 1
                else:
                    self.failures["llm_format_noncompliant"] += 1

                _, refs = parse_chat_response(raw_text)
                refs = self._filter_grounded_references(refs, rfx_ctx)
                if not refs:
                    refs = self._fallback_references_from_rfx(question)
                if not refs:
                    self.failures["refs_empty"] += 1
                    continue

                hm.clear_highlights()
                highlights = hm.add_highlights_from_references(refs)
                if highlights:
                    self.metrics.highlight_success += 1
                else:
                    self.failures["highlight_not_found"] += 1
                    first_ref = refs[0] if refs else {}
                    page = first_ref.get("page", "?")
                    snippet = str(first_ref.get("text", ""))[:60]
                    detail = f"highlight_not_found:page={page}:text={snippet}"
                    self.failure_details[detail] += 1
        finally:
            hm.close()

    @staticmethod
    def _build_context(rag: RAGEngine, query: str, label: str) -> str:
        results = rag.search(query, top_k=5)
        if not results:
            return f"[{label} 문맥 없음]"
        lines = []
        for r in results:
            page = r.metadata.get("page_number", -1)
            lines.append(f"[{label} 출처: {r.source_file}, page {page}] {r.text[:300]}")
        return "\n".join(lines)

    @staticmethod
    def _normalize_ref_text(text: str) -> str:
        normalized = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text or "").lower()
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _filter_grounded_references(self, refs: list[dict], rfx_context_text: str) -> list[dict]:
        if not refs:
            return []
        rfx_norm = self._normalize_ref_text(rfx_context_text)
        if not rfx_norm:
            return []

        grounded = []
        for ref in refs:
            page = int(ref.get("page", 0) or 0)
            if page <= 0:
                continue
            snippet = str(ref.get("text", "")).strip()
            if not snippet:
                grounded.append(ref)
                continue
            snippet_norm = self._normalize_ref_text(snippet)
            if not snippet_norm:
                continue
            if snippet_norm in rfx_norm:
                grounded.append(ref)
                continue
            keywords = [tok for tok in snippet_norm.split() if len(tok) >= 2][:6]
            hit_count = sum(1 for tok in keywords if tok in rfx_norm)
            if hit_count >= 2:
                grounded.append(ref)
        return grounded

    def _fallback_references_from_rfx(self, question: str) -> list[dict]:
        fallback_refs: list[dict] = []
        results = self.rfx_rag.search(question, top_k=3)
        for item in results:
            page = int(item.metadata.get("page_number", -1) or -1)
            if page <= 0:
                continue
            fallback_refs.append(
                {
                    "page": page,
                    "text": (item.text or "")[:80].strip(),
                }
            )
        return fallback_refs

    @staticmethod
    def _is_strict_json_format(raw_text: str) -> bool:
        try:
            data = json.loads(raw_text)
        except Exception:
            return False
        if not isinstance(data, dict):
            return False
        if "answer" not in data:
            return False
        if not isinstance(data.get("answer"), str):
            return False
        refs = data.get("references", [])
        if refs is None:
            refs = []
        if not isinstance(refs, list):
            return False
        for ref in refs:
            if not isinstance(ref, dict):
                return False
            if "page" not in ref:
                return False
        return True

    def _build_notes(self, top_failures: list[dict[str, Any]]) -> list[str]:
        notes = []
        rates = self.metrics.to_rates()
        if rates["llm_format_compliance_rate"] is not None and rates["llm_format_compliance_rate"] < 0.8:
            notes.append("LLM format compliance is below 80%; adjust prompt or model before Phase 1.5.")
        if top_failures and top_failures[0]["type"] == "highlight_not_found":
            notes.append("Top failure is highlight mapping; verify reference text span length and page metadata.")
        if not self.api_key:
            notes.append("OPENAI_API_KEY missing; LLM-dependent metrics are skipped/failed.")
        return notes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 0 baseline metrics.")
    parser.add_argument("--company", required=True, help="Company document path")
    parser.add_argument("--rfx", required=True, help="RFx document path")
    parser.add_argument("--model", default=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"))
    parser.add_argument("--out", default="reports/phase0_baseline.json", help="Output JSON report path")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    runner = Phase0BaselineRunner(
        company_path=args.company,
        rfx_path=args.rfx,
        model=args.model,
    )
    try:
        report = runner.run()
    finally:
        runner.cleanup()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSaved report to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
