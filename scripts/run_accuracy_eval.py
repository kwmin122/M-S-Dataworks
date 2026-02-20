#!/usr/bin/env python3
"""
범용 xlsx 평가 CLI.

사용법:
  python scripts/run_accuracy_eval.py --xlsx testdata/eval_default.xlsx
  python scripts/run_accuracy_eval.py --batch testdata/eval_files/ --threshold 0.90
  python scripts/run_accuracy_eval.py --out reports/accuracy_$(date +%Y%m%d).json

종료 규칙:
  any(file_accuracy < threshold) → exit(1)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from evaluator.accuracy import evaluate_xlsx, save_report


def main() -> None:
    parser = argparse.ArgumentParser(description="범용 xlsx 평가 CLI")
    parser.add_argument("--xlsx",         type=Path, default=None)
    parser.add_argument("--batch",        type=Path, default=None)
    parser.add_argument("--threshold",    type=float, default=0.90)
    parser.add_argument("--min-coverage", type=float, default=0.0)
    parser.add_argument("--out",          type=Path, default=None)
    args = parser.parse_args()

    targets: list = []
    if args.batch:
        targets = sorted(args.batch.glob("*.xlsx"))
        if not targets:
            print(f"⚠️ {args.batch} 에 .xlsx 파일이 없습니다.", file=sys.stderr)
            sys.exit(1)
    else:
        targets = [args.xlsx or Path("testdata/eval_default.xlsx")]

    reports = []
    for xlsx_file in targets:
        if not xlsx_file.exists():
            print(f"❌ 파일 없음: {xlsx_file}", file=sys.stderr)
            sys.exit(1)
        report = evaluate_xlsx(xlsx_file, args.threshold, args.min_coverage)
        reports.append(report)

        status = "✅ PASS" if report.passed else "❌ FAIL"
        denom = report.total - report.skipped
        print(
            f"{status} [{report.file}] "
            f"{report.passes}/{denom} = {report.accuracy:.1%} "
            f"(skip={report.skipped}, coverage={report.coverage:.1%})"
        )
        if not report.passed and report.fail_details:
            for d in report.fail_details[:5]:
                print(f"  - [{d['id']}] {d['question']}")

    # 전체 aggregate
    total_passes = sum(r.passes for r in reports)
    total_denom  = sum(r.total - r.skipped for r in reports)
    overall_acc  = total_passes / total_denom if total_denom > 0 else 0.0
    overall_ok   = all(r.passed for r in reports)
    print(f"\n{'✅' if overall_ok else '❌'} 전체 {total_passes}/{total_denom} = {overall_acc:.1%}")

    if args.out and len(reports) == 1:
        save_report(reports[0], args.out)
        print(f"📄 리포트: {args.out}")

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
