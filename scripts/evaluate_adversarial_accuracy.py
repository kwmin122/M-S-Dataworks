"""
Evaluate adversarial dataset accuracy against a gold answer key.

Usage:
    python scripts/evaluate_adversarial_accuracy.py \
      --company testdata/adversarial/company_adversarial.pdf \
      --rfx testdata/adversarial/rfx_adversarial.pdf \
      --answer-key testdata/adversarial/answer_key_adversarial_eval.json \
      --out reports/adversarial_accuracy_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine import RAGEngine
from matcher import MatchStatus, QualificationMatcher
from rfx_analyzer import RFxAnalyzer


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def _status_to_key(status: MatchStatus) -> str:
    if status == MatchStatus.MET:
        return "MET"
    if status == MatchStatus.PARTIALLY_MET:
        return "PARTIALLY_MET"
    if status == MatchStatus.NOT_MET:
        return "NOT_MET"
    return "UNKNOWN"


def _find_match_index(matches: list[dict[str, Any]], expected_desc: str) -> int:
    target = _normalize_text(expected_desc)
    for idx, item in enumerate(matches):
        if _normalize_text(item["description"]) == target:
            return idx
    for idx, item in enumerate(matches):
        if target in _normalize_text(item["description"]):
            return idx
    return -1


def run_evaluation(
    company_path: str,
    rfx_path: str,
    answer_key_path: str,
    model: str,
) -> dict[str, Any]:
    load_dotenv(".env")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in .env first.")

    with open(answer_key_path, "r", encoding="utf-8") as f:
        answer_key = json.load(f)

    analyzer = RFxAnalyzer(api_key=api_key, model=model)
    analysis = analyzer.analyze(rfx_path)

    temp_dir = tempfile.mkdtemp(prefix="adversarial_eval_")
    rag = RAGEngine(
        persist_directory=temp_dir,
        collection_name="company_adversarial_eval",
    )
    rag.clear_collection()
    rag.add_document(company_path)

    matcher = QualificationMatcher(rag_engine=rag, api_key=api_key, model=model)
    result = matcher.match(analysis)

    observed = [
        {
            "description": item.requirement.description,
            "status": _status_to_key(item.status),
            "confidence": item.confidence,
            "is_mandatory": item.requirement.is_mandatory,
        }
        for item in result.matches
    ]

    expected_items = answer_key.get("requirements", [])
    comparisons: list[dict[str, Any]] = []
    missing_expected = 0
    correct = 0

    for expected in expected_items:
        expected_desc = expected["description"]
        allowed_statuses = expected.get("allowed_statuses", [])
        idx = _find_match_index(observed, expected_desc)
        if idx < 0:
            missing_expected += 1
            comparisons.append(
                {
                    "description": expected_desc,
                    "allowed_statuses": allowed_statuses,
                    "actual_status": None,
                    "pass": False,
                    "reason": "expected_requirement_not_found",
                }
            )
            continue

        actual = observed[idx]
        is_pass = actual["status"] in allowed_statuses
        if is_pass:
            correct += 1
        comparisons.append(
            {
                "description": expected_desc,
                "allowed_statuses": allowed_statuses,
                "actual_status": actual["status"],
                "pass": is_pass,
                "confidence": actual["confidence"],
            }
        )

    total_expected = len(expected_items)
    accuracy = round(correct / total_expected, 4) if total_expected else 0.0

    recommendation_keywords = (
        answer_key.get("expected_gate", {}).get("allowed_recommendation_keywords", [])
    )
    recommendation = result.recommendation
    gate_pass = any(k.lower() in recommendation.lower() for k in recommendation_keywords)

    rag.clear_collection()

    return {
        "inputs": {
            "company_file": company_path,
            "rfx_file": rfx_path,
            "answer_key": answer_key_path,
            "model": model,
        },
        "summary": {
            "requirement_count_expected": total_expected,
            "requirement_count_observed": len(observed),
            "requirement_status_accuracy": accuracy,
            "requirement_correct": correct,
            "requirement_missing_expected": missing_expected,
            "gate_expected_keywords": recommendation_keywords,
            "gate_actual_recommendation": recommendation,
            "gate_pass": gate_pass,
            "overall_score": result.overall_score,
        },
        "comparisons": comparisons,
        "observed_matches": observed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate adversarial dataset accuracy")
    parser.add_argument("--company", required=True, help="Company PDF path")
    parser.add_argument("--rfx", required=True, help="RFx PDF path")
    parser.add_argument("--answer-key", required=True, help="Gold answer key JSON path")
    parser.add_argument("--out", required=True, help="Output report JSON path")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model name")
    args = parser.parse_args()

    report = run_evaluation(
        company_path=args.company,
        rfx_path=args.rfx,
        answer_key_path=args.answer_key,
        model=args.model,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Saved report to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
