"""
Railway 배포 전 E2E 체크리스트 실행기.

대상 스택: services/web_app (FastAPI) + rag_engine (FastAPI) + frontend/kirabot (React)
레거시 Streamlit UI (app.py)는 검사 대상 아님.

기본 동작:
1) 정적 검증(py_compile) — 프로덕션 핵심 파일
2) 핵심 회귀 테스트(pytest subset) — API, 검색, 매칭, 라우터
3) 핵심 의존성 import (fastapi, uvicorn, chromadb, pydantic)
4) 선택: 실서버 URL HTTP 점검
5) 결과를 Markdown 리포트로 저장

예시:
    python scripts/run_railway_predeploy_checklist.py \\
      --base-url https://your-railway-app.up.railway.app \\
      --out reports/railway_predeploy_checklist.md
"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    status: str  # PASS / FAIL / SKIP
    detail: str


def _run_command(command: Sequence[str], cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        list(command),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip()


def _http_get(url: str, timeout: int = 15) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "kira-predeploy-check/1.0"})
    with urlopen(request, timeout=timeout) as response:
        body = response.read(4096).decode("utf-8", errors="ignore")
        status = int(getattr(response, "status", 200))
        return status, body


def run_checks(base_url: str | None) -> list[CheckResult]:
    results: list[CheckResult] = []

    # Production stack: services/web_app + rag_engine (NOT legacy app.py/Streamlit)
    py_files = [
        "services/web_app/main.py",
        "matcher.py",
        "chat_router.py",
        "rfx_analyzer.py",
        "document_parser.py",
        "engine.py",
        "rag_engine/main.py",
    ]
    code, output = _run_command(["python", "-m", "py_compile", *py_files], ROOT_DIR)
    if code == 0:
        results.append(CheckResult("Python 문법 검사", "PASS", "핵심 파일 py_compile 통과"))
    else:
        results.append(CheckResult("Python 문법 검사", "FAIL", output[-1200:]))

    pytest_targets = [
        "tests/test_web_runtime_api.py",
        "tests/test_hybrid_search.py",
        "tests/test_constraint_evaluator.py",
        "tests/test_chat_router.py",
    ]
    code, output = _run_command(["pytest", "-q", *pytest_targets], ROOT_DIR)
    if code == 0:
        results.append(CheckResult("핵심 회귀 테스트", "PASS", output.splitlines()[-1] if output else "pytest 통과"))
    else:
        results.append(CheckResult("핵심 회귀 테스트", "FAIL", output[-1200:]))

    # Production core imports: FastAPI stack + RAG engine (NOT legacy Streamlit)
    core_imports = "import fastapi, uvicorn, chromadb, pydantic; print('ok')"
    code, output = _run_command(["python", "-c", core_imports], ROOT_DIR)
    if code == 0:
        results.append(CheckResult("핵심 의존성 import", "PASS", "fastapi, uvicorn, chromadb, pydantic import 성공"))
    else:
        results.append(CheckResult("핵심 의존성 import", "FAIL", output[-800:]))

    if not base_url:
        results.append(CheckResult("실서버 URL 점검", "SKIP", "--base-url 미지정"))
        return results

    normalized_base = base_url.rstrip("/")
    url_cases = [
        ("메인 페이지 (프론트엔드)", normalized_base, {200}),
        ("web_app health", f"{normalized_base}/api/health", {200}),
        ("web_app healthz", f"{normalized_base}/healthz", {200}),
        ("rag_engine 상태", f"{normalized_base}/api/debug/env", {200}),
        ("세션 생성", f"{normalized_base}/api/session", {200, 405}),  # GET→405, POST→200
    ]

    for name, url, expected_status_set in url_cases:
        try:
            status, body = _http_get(url)
            if status in expected_status_set:
                detail = f"HTTP {status}, 응답 길이 {len(body)}"
                results.append(CheckResult(name, "PASS", detail))
            else:
                expected_str = "/".join(str(item) for item in sorted(expected_status_set))
                detail = f"HTTP {status} (expected {expected_str})"
                results.append(CheckResult(name, "FAIL", detail))
        except Exception as exc:
            results.append(CheckResult(name, "FAIL", str(exc)))

    return results


def build_markdown(results: list[CheckResult]) -> str:
    now = datetime.now(timezone.utc).astimezone()
    lines = []
    lines.append("# Railway 배포 전 E2E 체크리스트 실행 결과")
    lines.append("")
    lines.append(f"- 실행 시각: {now.isoformat()}")
    lines.append("")
    lines.append("| 항목 | 상태 | 상세 |")
    lines.append("|------|------|------|")
    for result in results:
        detail = result.detail.replace("\n", " ").replace("|", "/")
        lines.append(f"| {result.name} | {result.status} | {detail} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Railway predeploy E2E checklist")
    parser.add_argument("--base-url", default="", help="실서버 URL (예: https://your-app.up.railway.app)")
    parser.add_argument(
        "--out",
        default="reports/railway_predeploy_checklist.md",
        help="결과 Markdown 파일 경로",
    )
    args = parser.parse_args()

    results = run_checks(base_url=args.base_url.strip() or None)
    markdown = build_markdown(results)

    output_path = (ROOT_DIR / args.out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print(markdown)
    has_failure = any(item.status == "FAIL" for item in results)
    return 1 if has_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
