"""
범용 정확도 평가 pytest 연동.
EVAL_XLSX 환경변수로 파일 교체 가능.
"""
import os
import json
import pytest
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluator.accuracy import evaluate_xlsx, EvalReport, save_report

EVAL_XLSX_DEFAULT = Path(__file__).parent.parent / "testdata" / "eval_default.xlsx"
EVAL_XLSX         = Path(os.getenv("EVAL_XLSX", str(EVAL_XLSX_DEFAULT)))
THRESHOLD         = float(os.getenv("EVAL_ACCURACY_THRESHOLD", "0.90"))
REPORT_DIR        = Path(__file__).parent.parent / "reports"


def test_eval_accuracy_summary():
    """
    평가 파일이 있고 J열 판정이 있으면 정확도 ≥ threshold.
    파일 없음 또는 판정 없음 → skip.
    """
    if not EVAL_XLSX.exists():
        pytest.skip(f"평가 파일 없음: {EVAL_XLSX}  (testdata/eval_default.xlsx 준비 필요)")

    report = evaluate_xlsx(EVAL_XLSX, THRESHOLD)

    if report.total - report.skipped == 0:
        pytest.skip("J열에 PASS/FAIL 판정 없음")

    # 리포트 저장
    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / f"accuracy_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    save_report(report, report_path)
    print(f"\n정확도: {report.passes}/{report.total - report.skipped} = {report.accuracy:.1%} "
          f"(skip={report.skipped}, coverage={report.coverage:.1%})")
    print(f"리포트: {report_path}")

    assert report.accuracy >= THRESHOLD, (
        f"정확도 {report.accuracy:.1%} < 목표 {THRESHOLD:.0%}. "
        f"FAIL {report.fails}건, SKIP {report.skipped}건"
    )
