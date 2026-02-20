"""
Kira Web Runtime 문서분석 스모크 테스트.

실행 예시:
python scripts/smoke_test_document_analysis.py \
  --company testdata/adversarial/company_adversarial_ko.pdf \
  --target testdata/adversarial/rfx_adversarial_ko.pdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from services.web_app.main import app


def _pp(title: str, payload: Any) -> None:
    print(f"\n[{title}]")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)


def _require_ok(response, step: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise RuntimeError(f"{step} 실패 ({response.status_code}): {response.text}")
    data = response.json()
    if isinstance(data, dict) and data.get("ok") is False:
        raise RuntimeError(f"{step} 실패 (ok=false): {data}")
    return data


def run(company_file: Path, target_file: Path) -> None:
    if not company_file.exists():
        raise FileNotFoundError(f"회사 문서 없음: {company_file}")
    if not target_file.exists():
        raise FileNotFoundError(f"분석 문서 없음: {target_file}")

    client = TestClient(app)

    # 1) 세션 생성
    resp = client.post("/api/session")
    session_data = _require_ok(resp, "세션 생성")
    session_id = session_data["session_id"]
    _pp("session", session_data)

    # 2) 회사 문서 업로드
    with company_file.open("rb") as handle:
        resp = client.post(
            "/api/company/upload",
            data={"session_id": session_id},
            files={"files": (company_file.name, handle, "application/pdf")},
        )
    company_data = _require_ok(resp, "회사 문서 업로드")
    _pp("company_upload", company_data)

    # 3) 분석 문서 업로드 + 분석
    with target_file.open("rb") as handle:
        resp = client.post(
            "/api/analyze/upload",
            data={"session_id": session_id},
            files={"file": (target_file.name, handle, "application/pdf")},
        )
    analyze_data = _require_ok(resp, "분석 실행")
    _pp(
        "analyze_summary",
        {
            "ok": analyze_data.get("ok"),
            "filename": analyze_data.get("filename"),
            "overall_score": analyze_data.get("matching", {}).get("overall_score"),
            "recommendation": analyze_data.get("matching", {}).get("recommendation"),
            "quota": analyze_data.get("quota", {}),
        },
    )

    # 4) 오프토픽 차단 검증
    resp = client.post("/api/chat", json={"session_id": session_id, "message": "배고파"})
    offtopic_data = _require_ok(resp, "오프토픽 질의")
    _pp(
        "chat_offtopic",
        {
            "blocked": offtopic_data.get("blocked"),
            "policy": offtopic_data.get("policy"),
            "intent": offtopic_data.get("intent"),
            "answer": str(offtopic_data.get("answer", ""))[:120],
            "quota": offtopic_data.get("quota", {}),
        },
    )

    # 5) 도메인 질의 검증
    resp = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "이 공고 필수요건을 요약해줘"},
    )
    domain_data = _require_ok(resp, "도메인 질의")
    _pp(
        "chat_domain",
        {
            "blocked": domain_data.get("blocked"),
            "policy": domain_data.get("policy"),
            "intent": domain_data.get("intent"),
            "answer_preview": str(domain_data.get("answer", ""))[:200],
            "references_count": len(domain_data.get("references", []) or []),
            "quota": domain_data.get("quota", {}),
        },
    )

    # 6) 사용량 집계 확인
    resp = client.post("/api/usage/me", json={"session_id": session_id})
    usage_data = _require_ok(resp, "사용량 조회")
    _pp("usage_me", usage_data)

    print("\n✅ 스모크 테스트 완료")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kira 문서분석 스모크 테스트")
    parser.add_argument("--company", required=True, help="회사 문서 파일 경로")
    parser.add_argument("--target", required=True, help="분석할 문서 파일 경로")
    args = parser.parse_args()
    run(company_file=Path(args.company), target_file=Path(args.target))


if __name__ == "__main__":
    main()
