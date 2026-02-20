"""
범용 xlsx 평가 파이프라인 - 공유 핵심 함수.
run_accuracy_eval.py와 tests/test_evaluation_accuracy.py가 같은 함수를 사용.
드리프트 방지: 로직은 이 파일 한 곳에만.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


@dataclass
class EvalReport:
    file: str
    total: int
    passes: int
    fails: int
    skipped: int             # J열 빈값·오탈자 카운트
    accuracy: float          # passes / (total - skipped); 분모 0이면 0.0
    coverage: float          # (total - skipped) / total; 0이면 0.0
    threshold: float
    min_coverage: float      # 커버리지 하한 (기본 0.0 = 비활성)
    passed: bool             # accuracy≥threshold AND coverage≥min_coverage (분모 0 → False)
    fail_details: list = field(default_factory=list)  # [{id, question}]


def _find_column_indices(header_row: tuple) -> dict:
    """
    헤더명 우선 컬럼 매핑.
    없으면 A/C/J 인덱스 fallback.
    """
    name_map = {
        "id": ["id", "번호", "no"],
        "question": ["질문", "question"],
        "judgment": ["판정", "judgment", "pass/fail", "pass_fail"],
    }
    result: dict = {}
    if header_row:
        header = [str(h).strip().lower() if h else "" for h in header_row]
        for field_name, candidates in name_map.items():
            for i, h in enumerate(header):
                if any(c in h for c in candidates):
                    result[field_name] = i
                    break
    # fallback: A=0, C=2, J=9
    result.setdefault("id", 0)
    result.setdefault("question", 2)
    result.setdefault("judgment", 9)
    return result


def evaluate_xlsx(
    xlsx_path: Path,
    threshold: float = 0.90,
    min_coverage: float = 0.0,
) -> EvalReport:
    """
    xlsx 평가 파일로 정확도를 측정한다.

    J열 규칙:
    - "PASS" (대소문자 무관) → passes + 1
    - "FAIL" (대소문자 무관) → fails + 1
    - 빈값 / 오탈자 → skipped + 1

    분모 = total - skipped
    분모 == 0이면 accuracy=0.0, passed=False
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl 미설치: pip install openpyxl")

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return EvalReport(
            file=xlsx_path.name, total=0, passes=0, fails=0,
            skipped=0, accuracy=0.0, coverage=0.0,
            threshold=threshold, min_coverage=min_coverage, passed=False,
        )

    col = _find_column_indices(rows[0])
    data_rows = rows[1:]  # 헤더 제외

    total = passes = fails = skipped = 0
    fail_details: list = []

    for row in data_rows:
        if not row or not row[col["id"]]:
            continue                  # 빈 행 스킵
        total += 1
        raw_judgment = row[col["judgment"]] if len(row) > col["judgment"] else None
        judgment = str(raw_judgment).strip().upper() if raw_judgment else ""

        if judgment == "PASS":
            passes += 1
        elif judgment == "FAIL":
            fails += 1
            fail_details.append({
                "id": str(row[col["id"]]),
                "question": str(row[col["question"]]) if len(row) > col["question"] else "",
            })
        else:
            skipped += 1   # 빈값·오탈자

    denominator = total - skipped
    accuracy = passes / denominator if denominator > 0 else 0.0
    coverage = denominator / total if total > 0 else 0.0

    if denominator == 0:
        passed = False
    else:
        passed = (accuracy >= threshold) and (
            min_coverage <= 0.0 or coverage >= min_coverage
        )

    return EvalReport(
        file=xlsx_path.name,
        total=total,
        passes=passes,
        fails=fails,
        skipped=skipped,
        accuracy=accuracy,
        coverage=coverage,
        threshold=threshold,
        min_coverage=min_coverage,
        passed=passed,
        fail_details=fail_details,
    )


def save_report(report: EvalReport, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "date": datetime.now().isoformat(),
        "file": report.file,
        "total": report.total,
        "passes": report.passes,
        "fails": report.fails,
        "skipped": report.skipped,
        "accuracy": report.accuracy,
        "coverage": report.coverage,
        "threshold": report.threshold,
        "min_coverage": report.min_coverage,
        "passed": report.passed,
        "fail_details": report.fail_details[:20],  # 상위 20건만
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
