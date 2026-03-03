"""Phase 2 실전 파이프라인 테스트 — 9개 실제 RFP 문서.

각 문서를 파싱 → 메타데이터 추출 → WBS/PPT/실적기술서 생성 → 품질 평가.
LLM 없이 fallback 경로로 구조/파일 생성을 검증.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

# Root-level parser (supports HWP)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "rag_engine"))

from document_parser import DocumentParser

from phase2_models import (
    MethodologyType, WbsTask, PersonnelAllocation,
    SlideType, SlideContent, QnaPair,
    TrackRecordEntry, PersonnelEntry,
)
from wbs_planner import (
    _extract_project_duration, _detect_methodology,
    _fallback_tasks, _allocate_personnel, _TEMPLATES,
)
from wbs_generator import generate_wbs_xlsx, generate_gantt_chart, generate_wbs_docx
from ppt_slide_planner import plan_slides
from ppt_assembler import assemble_pptx
from track_record_assembler import assemble_track_record_docx


# ── 문서 목록 ──
DOCS = [
    {
        "path": os.path.expanduser("~/Downloads/1. 입찰공고서(공고번호_R26BK01265177-000, 봉사단교육체계DX).hwp"),
        "short": "봉사단교육체계DX",
        "expected": {
            "type": "용역",
            "has_title": True,
        },
    },
    {
        "path": os.path.expanduser("~/Downloads/입찰재공고서.pdf"),
        "short": "입찰재공고서",
        "expected": {"type": "용역", "has_title": True},
    },
    {
        "path": os.path.expanduser("~/Downloads/입찰재공고문(2026년 선박검사관 교육·훈련 위탁용역 계획).pdf"),
        "short": "선박검사관교육",
        "expected": {"type": "교육", "has_title": True},
    },
    {
        "path": os.path.expanduser("~/Downloads/입찰공고서(긴급)-일반,9999, 수평, 공가, 90.pdf"),
        "short": "긴급입찰공고",
        "expected": {"type": "일반", "has_title": True},
    },
    {
        "path": os.path.expanduser("~/Downloads/입찰공고서_국가_1468-0036_조평오프_정량_정성_차등3_필수.pdf"),
        "short": "국가1468정량정성",
        "expected": {"type": "용역", "has_title": True},
    },
    {
        "path": os.path.expanduser("~/Downloads/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf"),
        "short": "공공데이터컨설팅",
        "expected": {"type": "컨설팅", "has_title": True},
    },
    {
        "path": os.path.expanduser("~/Downloads/붙임2_2026년도 공공저작물 디지털 전환 구축 사업_제안요청서.hwp"),
        "short": "공공저작물DX",
        "expected": {"type": "용역", "has_title": True},
    },
    {
        "path": os.path.expanduser("~/Downloads/공사입찰설명서(국가,건축,100억미만).hwp"),
        "short": "건축공사100억",
        "expected": {"type": "공사", "has_title": True},
    },
    {
        "path": os.path.expanduser("~/Downloads/공고서_국가_일반_국제_정보화전략계획_1468_20억미만_공동이행_하도급사전승인_차등점수제_서면.pdf"),
        "short": "정보화전략계획",
        "expected": {"type": "용역", "has_title": True},
    },
]


# ── regex 기반 RFP 메타 추출 ──

def extract_rfp_meta(text: str, filename: str) -> dict[str, Any]:
    """파싱된 텍스트에서 regex로 RFP 메타데이터 추출."""
    meta: dict[str, Any] = {
        "title": "",
        "issuing_org": "",
        "budget": "",
        "project_period": "",
        "deadline": "",
        "announcement_number": "",
    }

    # 사업명 추출 패턴
    title_patterns = [
        r"사\s*업\s*명\s*[:：]\s*(.+?)(?:\n|$)",
        r"건\s*명\s*[:：]\s*(.+?)(?:\n|$)",
        r"용\s*역\s*명\s*[:：]\s*(.+?)(?:\n|$)",
        r"공\s*사\s*명\s*[:：]\s*(.+?)(?:\n|$)",
        r"입\s*찰\s*건\s*명\s*[:：]\s*(.+?)(?:\n|$)",
        r"과\s*업\s*명\s*[:：]\s*(.+?)(?:\n|$)",
    ]
    for pat in title_patterns:
        m = re.search(pat, text)
        if m and len(m.group(1).strip()) > 3:
            meta["title"] = m.group(1).strip()[:100]
            break

    # 파일명에서 힌트 추출 (fallback)
    if not meta["title"]:
        # 파일명 기반 fallback
        name = os.path.splitext(os.path.basename(filename))[0]
        # 괄호 안 내용, 언더스코어 처리
        cleaned = re.sub(r"[_\-]", " ", name)
        if len(cleaned) > 5:
            meta["title"] = cleaned[:80]

    # 발주기관
    org_patterns = [
        r"(?:발주(?:기관|처|부서)|수요기관|계약(?:기관|부서))\s*[:：]\s*(.+?)(?:\n|$)",
        r"(?:발\s*주\s*처)\s*[:：]\s*(.+?)(?:\n|$)",
    ]
    for pat in org_patterns:
        m = re.search(pat, text)
        if m:
            meta["issuing_org"] = m.group(1).strip()[:50]
            break

    # 예산/사업비
    budget_patterns = [
        r"(?:추정(?:가격|금액)|사업비|예산(?:금액)?|배정예산|계약금액)\s*[:：]?\s*([\d,\.]+\s*(?:원|천원|백만원|억원|만원))",
        r"([\d,]+)\s*원\s*(?:\(|정)",
    ]
    for pat in budget_patterns:
        m = re.search(pat, text)
        if m:
            meta["budget"] = m.group(1).strip() if pat == budget_patterns[0] else m.group(0).strip()
            break

    # 사업기간
    period_patterns = [
        r"(?:사업|계약|용역|수행)\s*기간\s*[:：]?\s*(.+?)(?:\n|$)",
        r"(?:납품|이행)\s*기한\s*[:：]?\s*(.+?)(?:\n|$)",
        r"(\d+)\s*개월",
    ]
    for pat in period_patterns:
        m = re.search(pat, text)
        if m:
            meta["project_period"] = m.group(1).strip()[:50] if "개월" not in pat else m.group(0).strip()
            break

    # 공고번호
    num_patterns = [
        r"공고\s*번호\s*[:：]?\s*([\w\-]+)",
        r"(R\d{2}[A-Z]{2}\d+(?:\-\d+)?)",
    ]
    for pat in num_patterns:
        m = re.search(pat, text)
        if m:
            meta["announcement_number"] = m.group(1).strip()
            break

    # 마감일
    deadline_patterns = [
        r"(?:입찰|제안서?\s*제출)\s*(?:마감|기한)\s*[:：]?\s*(\d{4}[\.\-/]\s*\d{1,2}[\.\-/]\s*\d{1,2})",
        r"(\d{4})[\.\-년]\s*(\d{1,2})[\.\-월]\s*(\d{1,2})[\.\-일]?\s*(?:\d{1,2}:\d{2})?(?:.*?마감|까지)",
    ]
    for pat in deadline_patterns:
        m = re.search(pat, text)
        if m:
            meta["deadline"] = m.group(0).strip()[:40]
            break

    return meta


@dataclass
class DocTestResult:
    """단일 문서 테스트 결과."""
    doc_short: str
    parse_ok: bool = False
    char_count: int = 0
    page_count: int = 0
    meta: dict = field(default_factory=dict)
    methodology: str = ""
    duration_months: int = 0
    wbs_task_count: int = 0
    xlsx_ok: bool = False
    xlsx_size: int = 0
    gantt_ok: bool = False
    gantt_size: int = 0
    wbs_docx_ok: bool = False
    wbs_docx_size: int = 0
    pptx_ok: bool = False
    pptx_size: int = 0
    pptx_slide_count: int = 0
    track_record_ok: bool = False
    track_record_size: int = 0
    errors: list = field(default_factory=list)
    parse_time: float = 0.0
    gen_time: float = 0.0


def _dummy_track_records(title: str) -> list[TrackRecordEntry]:
    """테스트용 더미 실적 데이터."""
    return [
        TrackRecordEntry(
            project_name=f"{title} 유사 프로젝트 1",
            client="OO기관",
            period="2024.01~2024.08",
            amount=15.0,
            description="유사 프로젝트 수행 경험",
            technologies=["Python", "FastAPI"],
            relevance_score=0.85,
            generated_text=f"본 프로젝트는 {title}과 유사한 범위의 사업을 성공적으로 수행한 경험입니다.",
        ),
        TrackRecordEntry(
            project_name=f"{title} 유사 프로젝트 2",
            client="XX부",
            period="2023.05~2024.02",
            amount=20.0,
            description="관련 기술 적용 프로젝트",
            technologies=["React", "PostgreSQL"],
            relevance_score=0.72,
            generated_text="해당 사업에서 요구하는 핵심 기술 스택을 활용한 프로젝트를 수행하였습니다.",
        ),
    ]


def _dummy_personnel() -> list[PersonnelEntry]:
    """테스트용 더미 인력 데이터."""
    return [
        PersonnelEntry(
            name="홍길동", role="PM", grade="특급", experience_years=18,
            certifications=["PMP", "정보관리기술사"],
            key_projects=["유사 프로젝트 PM 경험"],
            generated_text="18년 경력의 PM으로 다수의 공공 프로젝트를 성공적으로 이끌었습니다.",
        ),
        PersonnelEntry(
            name="김영희", role="PL", grade="고급", experience_years=12,
            certifications=["정보처리기사"],
            key_projects=["기술 리더 경험"],
            generated_text="12년간 시스템 개발 및 기술 리드를 수행한 전문가입니다.",
        ),
    ]


def run_single_doc_test(doc_info: dict, output_base: str) -> DocTestResult:
    """단일 문서에 대해 전체 파이프라인 테스트."""
    result = DocTestResult(doc_short=doc_info["short"])
    filepath = doc_info["path"]
    doc_outdir = os.path.join(output_base, result.doc_short)
    os.makedirs(doc_outdir, exist_ok=True)

    # ── Step 1: 문서 파싱 ──
    t0 = time.time()
    try:
        parser = DocumentParser(chunk_size=900, chunk_overlap=150)
        parsed = parser.parse(filepath)
        result.parse_ok = True
        result.char_count = parsed.char_count
        result.page_count = parsed.page_count
        raw_text = parsed.text
    except Exception as exc:
        result.errors.append(f"PARSE FAIL: {exc}")
        result.parse_time = round(time.time() - t0, 2)
        return result
    result.parse_time = round(time.time() - t0, 2)

    if result.char_count < 50:
        result.errors.append(f"텍스트 너무 짧음: {result.char_count}자")
        return result

    # ── Step 2: 메타데이터 추출 (regex) ──
    meta = extract_rfp_meta(raw_text, filepath)
    result.meta = meta

    # RFP dict 조립
    rfx_result = {
        "title": meta["title"] or doc_info["short"],
        "issuing_org": meta["issuing_org"],
        "budget": meta["budget"],
        "project_period": meta["project_period"],
        "requirements": [],
        "evaluation_criteria": [],
        "rfp_text_summary": raw_text[:2000],
    }

    # ── Step 3: 방법론 감지 + 기간 추출 ──
    methodology = _detect_methodology(rfx_result)
    result.methodology = methodology.value
    duration = _extract_project_duration(rfx_result)
    if duration <= 0 or duration > 36:
        duration = 6  # safe default
    result.duration_months = duration

    # ── Step 4: WBS 생성 (LLM 시도 → Fallback) ──
    t1 = time.time()
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            from wbs_planner import plan_wbs
            try:
                tasks, personnel_alloc, duration, methodology = plan_wbs(
                    rfx_result, methodology=methodology, total_months=duration, api_key=api_key,
                )
                result.wbs_task_count = len(tasks)
                result.duration_months = duration
                result.methodology = methodology.value
            except Exception as llm_exc:
                result.errors.append(f"WBS LLM failed, using fallback: {llm_exc}")
                template = _TEMPLATES[methodology]
                tasks = _fallback_tasks(template, duration)
                personnel_alloc = _allocate_personnel(tasks, duration)
                result.wbs_task_count = len(tasks)
        else:
            template = _TEMPLATES[methodology]
            tasks = _fallback_tasks(template, duration)
            personnel_alloc = _allocate_personnel(tasks, duration)
            result.wbs_task_count = len(tasks)

        title_safe = re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", doc_info["short"])[:50]

        # XLSX
        xlsx_path = os.path.join(doc_outdir, f"{title_safe}_WBS.xlsx")
        generate_wbs_xlsx(tasks, personnel_alloc, rfx_result["title"], duration, xlsx_path)
        if os.path.isfile(xlsx_path):
            result.xlsx_ok = True
            result.xlsx_size = os.path.getsize(xlsx_path)

        # 간트차트
        gantt_path = os.path.join(doc_outdir, f"{title_safe}_Gantt.png")
        generate_gantt_chart(tasks, duration, gantt_path)
        if os.path.isfile(gantt_path):
            result.gantt_ok = True
            result.gantt_size = os.path.getsize(gantt_path)

        # 수행계획서 DOCX
        wbs_docx_path = os.path.join(doc_outdir, f"{title_safe}_수행계획서.docx")
        generate_wbs_docx(
            tasks, personnel_alloc, rfx_result["title"],
            duration, methodology.value, wbs_docx_path, gantt_path,
        )
        if os.path.isfile(wbs_docx_path):
            result.wbs_docx_ok = True
            result.wbs_docx_size = os.path.getsize(wbs_docx_path)

    except Exception as exc:
        result.errors.append(f"WBS FAIL: {exc}\n{traceback.format_exc()}")

    # ── Step 5: PPT 생성 ──
    try:
        slides = plan_slides(rfx_result, target_slide_count=15, duration_min=20)
        qna_pairs = [
            QnaPair(question="본 사업의 핵심 성공 요소는?", answer="체계적 프로젝트 관리와 전문 인력 투입입니다.", category="관리"),
            QnaPair(question="일정 지연 시 대응 방안은?", answer="주간 진도 점검과 완충 기간 활용으로 대응합니다.", category="관리"),
            QnaPair(question="품질 보증 방안은?", answer="단계별 품질 검토와 독립 QA 수행으로 보장합니다.", category="기술"),
        ]

        pptx_path = os.path.join(doc_outdir, f"{title_safe}_PT.pptx")
        assemble_pptx(
            title=rfx_result["title"],
            slides=slides,
            qna_pairs=qna_pairs,
            output_path=pptx_path,
            company_name="(주)MS솔루션즈",
        )
        if os.path.isfile(pptx_path):
            result.pptx_ok = True
            result.pptx_size = os.path.getsize(pptx_path)
            result.pptx_slide_count = len(slides)

    except Exception as exc:
        result.errors.append(f"PPT FAIL: {exc}\n{traceback.format_exc()}")

    # ── Step 6: 실적/경력 기술서 ──
    try:
        records = _dummy_track_records(rfx_result["title"])
        personnel_entries = _dummy_personnel()

        tr_path = os.path.join(doc_outdir, f"{title_safe}_실적기술서.docx")
        assemble_track_record_docx(
            title=f"{rfx_result['title']} - 유사수행실적 기술서",
            records=records,
            personnel=personnel_entries,
            output_path=tr_path,
        )
        if os.path.isfile(tr_path):
            result.track_record_ok = True
            result.track_record_size = os.path.getsize(tr_path)

    except Exception as exc:
        result.errors.append(f"TRACK_RECORD FAIL: {exc}\n{traceback.format_exc()}")

    result.gen_time = round(time.time() - t1, 2)
    return result


def print_report(results: list[DocTestResult]):
    """전체 테스트 보고서 출력."""
    print("\n" + "=" * 100)
    print("Phase 2 실전 RFP 파이프라인 테스트 보고서")
    print("=" * 100)

    # ── 1. 파싱 결과 ──
    print("\n## 1. 문서 파싱 결과")
    print(f"{'문서':<20} {'파싱':>5} {'글자수':>8} {'페이지':>5} {'시간':>6} {'사업명':<40}")
    print("-" * 100)
    for r in results:
        status = "OK" if r.parse_ok else "FAIL"
        title = (r.meta.get("title", "") or "-")[:38]
        print(f"{r.doc_short:<20} {status:>5} {r.char_count:>8,} {r.page_count:>5} {r.parse_time:>5.1f}s {title:<40}")

    # ── 2. 메타데이터 추출 ──
    print("\n## 2. 메타데이터 추출 결과")
    print(f"{'문서':<20} {'발주처':<20} {'예산':<20} {'기간':<15} {'공고번호':<25}")
    print("-" * 100)
    for r in results:
        if not r.parse_ok:
            continue
        m = r.meta
        print(f"{r.doc_short:<20} {(m.get('issuing_org','') or '-')[:18]:<20} "
              f"{(m.get('budget','') or '-')[:18]:<20} "
              f"{(m.get('project_period','') or '-')[:13]:<15} "
              f"{(m.get('announcement_number','') or '-')[:23]:<25}")

    # ── 3. 방법론/기간 추론 ──
    print("\n## 3. 방법론/기간 추론")
    print(f"{'문서':<20} {'방법론':<12} {'기간(월)':>8} {'WBS태스크':>10}")
    print("-" * 60)
    for r in results:
        if not r.parse_ok:
            continue
        print(f"{r.doc_short:<20} {r.methodology:<12} {r.duration_months:>8} {r.wbs_task_count:>10}")

    # ── 4. 파일 생성 결과 ──
    print("\n## 4. 파일 생성 결과")
    print(f"{'문서':<20} {'XLSX':>8} {'Gantt':>8} {'WBS DOCX':>10} {'PPTX':>8} {'슬라이드':>8} {'실적DOCX':>10} {'생성시간':>8}")
    print("-" * 100)
    for r in results:
        if not r.parse_ok:
            print(f"{r.doc_short:<20} {'SKIP':>8} {'SKIP':>8} {'SKIP':>10} {'SKIP':>8} {'SKIP':>8} {'SKIP':>10} {'-':>8}")
            continue
        xlsx_s = f"{r.xlsx_size//1024}KB" if r.xlsx_ok else "FAIL"
        gantt_s = f"{r.gantt_size//1024}KB" if r.gantt_ok else "FAIL"
        wbs_s = f"{r.wbs_docx_size//1024}KB" if r.wbs_docx_ok else "FAIL"
        pptx_s = f"{r.pptx_size//1024}KB" if r.pptx_ok else "FAIL"
        slides = str(r.pptx_slide_count) if r.pptx_ok else "-"
        tr_s = f"{r.track_record_size//1024}KB" if r.track_record_ok else "FAIL"
        print(f"{r.doc_short:<20} {xlsx_s:>8} {gantt_s:>8} {wbs_s:>10} {pptx_s:>8} {slides:>8} {tr_s:>10} {r.gen_time:>7.1f}s")

    # ── 5. 에러 요약 ──
    all_errors = [(r.doc_short, e) for r in results for e in r.errors]
    if all_errors:
        print(f"\n## 5. 에러 ({len(all_errors)}건)")
        for doc_name, err in all_errors:
            # 첫 줄만 표시
            first_line = err.split("\n")[0][:120]
            print(f"  [{doc_name}] {first_line}")

    # ── 6. 종합 점수 ──
    print("\n## 6. 종합 점수")
    total = len(results)
    parse_ok = sum(1 for r in results if r.parse_ok)
    xlsx_ok = sum(1 for r in results if r.xlsx_ok)
    gantt_ok = sum(1 for r in results if r.gantt_ok)
    wbs_ok = sum(1 for r in results if r.wbs_docx_ok)
    pptx_ok = sum(1 for r in results if r.pptx_ok)
    tr_ok = sum(1 for r in results if r.track_record_ok)

    items = [
        ("파싱 성공", parse_ok, total),
        ("XLSX 생성", xlsx_ok, total),
        ("간트차트 PNG", gantt_ok, total),
        ("수행계획서 DOCX", wbs_ok, total),
        ("PPT 발표자료", pptx_ok, total),
        ("실적/경력 기술서", tr_ok, total),
    ]

    for label, ok, tot in items:
        pct = ok / tot * 100 if tot > 0 else 0
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        print(f"  {label:<20} {bar} {ok}/{tot} ({pct:.0f}%)")

    # ── 7. 메타데이터 품질 점수 ──
    print("\n## 7. 메타데이터 추출 품질")
    fields = ["title", "issuing_org", "budget", "project_period", "announcement_number"]
    for f_name in fields:
        extracted = sum(1 for r in results if r.parse_ok and r.meta.get(f_name))
        parseable = parse_ok
        pct = extracted / parseable * 100 if parseable > 0 else 0
        print(f"  {f_name:<25} {extracted}/{parseable} ({pct:.0f}%)")

    print("\n" + "=" * 100)
    return results


def _load_env():
    """rag_engine/.env에서 환경변수 로드."""
    env_path = os.path.join(ROOT, "rag_engine", ".env")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    val = val.strip().strip('"').strip("'")
                    if key.strip() and val:
                        os.environ.setdefault(key.strip(), val)


def main():
    _load_env()
    print(f"OPENAI_API_KEY: {'SET' if os.environ.get('OPENAI_API_KEY') else 'NOT SET'}")

    output_base = os.path.expanduser("~/Desktop/phase2_rfp_test")
    os.makedirs(output_base, exist_ok=True)

    results = []
    for i, doc_info in enumerate(DOCS, 1):
        print(f"\n{'─'*60}")
        print(f"[{i}/{len(DOCS)}] {doc_info['short']}")
        print(f"  파일: {os.path.basename(doc_info['path'])}")
        print(f"  크기: {os.path.getsize(doc_info['path']):,} bytes")
        r = run_single_doc_test(doc_info, output_base)
        results.append(r)
        if r.parse_ok:
            files_ok = sum([r.xlsx_ok, r.gantt_ok, r.wbs_docx_ok, r.pptx_ok, r.track_record_ok])
            print(f"  => 파싱 OK ({r.char_count:,}자, {r.page_count}페이지)")
            print(f"  => 파일 생성: {files_ok}/5")
            if r.meta.get("title"):
                print(f"  => 사업명: {r.meta['title'][:50]}")
        else:
            print(f"  => 파싱 FAIL")
        for err in r.errors:
            print(f"  => ERROR: {err.split(chr(10))[0][:80]}")

    report = print_report(results)

    # JSON 저장
    json_path = os.path.join(output_base, "test_report.json")
    json_data = []
    for r in results:
        json_data.append({
            "doc": r.doc_short,
            "parse_ok": r.parse_ok,
            "char_count": r.char_count,
            "page_count": r.page_count,
            "meta": r.meta,
            "methodology": r.methodology,
            "duration_months": r.duration_months,
            "wbs_task_count": r.wbs_task_count,
            "files": {
                "xlsx": {"ok": r.xlsx_ok, "size": r.xlsx_size},
                "gantt": {"ok": r.gantt_ok, "size": r.gantt_size},
                "wbs_docx": {"ok": r.wbs_docx_ok, "size": r.wbs_docx_size},
                "pptx": {"ok": r.pptx_ok, "size": r.pptx_size, "slides": r.pptx_slide_count},
                "track_record": {"ok": r.track_record_ok, "size": r.track_record_size},
            },
            "errors": r.errors,
        })
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"\n상세 결과: {json_path}")
    print(f"생성 파일: {output_base}/")


if __name__ == "__main__":
    main()
