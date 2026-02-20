"""
라우터 텔레메트리(JSONL) 요약 스크립트.

사용 예시:
    python scripts/analyze_router_logs.py \
      --input reports/router_telemetry.jsonl \
      --output reports/router_telemetry_summary.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int(round((len(sorted_values) - 1) * (p / 100.0)))
    return sorted_values[max(0, min(index, len(sorted_values) - 1))]


def load_events(path: Path) -> list[dict]:
    events: list[dict] = []
    if not path.exists():
        return events

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
    return events


def render_markdown(events: list[dict], source_path: Path) -> str:
    if not events:
        return (
            "# Router Telemetry Summary\n\n"
            f"- input: `{source_path}`\n"
            "- events: 0\n"
            "- 유효 이벤트가 없어 분석할 데이터가 없습니다.\n"
        )

    intent_counter = Counter(str(event.get("intent", "UNKNOWN")) for event in events)
    policy_counter = Counter(str(event.get("policy", "UNKNOWN")) for event in events)
    relevance_values = [float(event.get("relevance_score", 0.0) or 0.0) for event in events]
    confidence_values = [float(event.get("confidence", 0.0) or 0.0) for event in events]
    llm_calls = sum(1 for event in events if bool(event.get("llm_called")))

    lines: list[str] = []
    lines.append("# Router Telemetry Summary")
    lines.append("")
    lines.append(f"- input: `{source_path}`")
    lines.append(f"- events: {len(events)}")
    lines.append(f"- llm_called: {llm_calls} ({(llm_calls / len(events)) * 100:.1f}%)")
    lines.append("")

    lines.append("## Intent Distribution")
    for intent, count in intent_counter.most_common():
        lines.append(f"- {intent}: {count}")
    lines.append("")

    lines.append("## Policy Distribution")
    for policy, count in policy_counter.most_common():
        lines.append(f"- {policy}: {count}")
    lines.append("")

    lines.append("## Relevance Score Percentiles")
    lines.append(f"- P10: {percentile(relevance_values, 10):.4f}")
    lines.append(f"- P20: {percentile(relevance_values, 20):.4f}")
    lines.append(f"- P30: {percentile(relevance_values, 30):.4f}")
    lines.append(f"- P50: {percentile(relevance_values, 50):.4f}")
    lines.append("")

    lines.append("## Router Confidence Percentiles")
    lines.append(f"- P10: {percentile(confidence_values, 10):.4f}")
    lines.append(f"- P50: {percentile(confidence_values, 50):.4f}")
    lines.append(f"- P90: {percentile(confidence_values, 90):.4f}")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="라우터 텔레메트리 분석")
    parser.add_argument(
        "--input",
        default="./reports/router_telemetry.jsonl",
        help="입력 JSONL 파일 경로",
    )
    parser.add_argument(
        "--output",
        default="",
        help="출력 Markdown 파일 경로 (미지정 시 stdout)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    events = load_events(input_path)
    markdown = render_markdown(events=events, source_path=input_path)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(f"✅ 요약 저장: {output_path}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()

