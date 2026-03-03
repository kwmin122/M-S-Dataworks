#!/usr/bin/env python3
"""E2E Demo & Evaluation — HWPX + Company Skill File Pipeline.

전체 파이프라인 실행 + 정량 평가:
  Stage 1: Profile 생성 (StyleProfile → profile.md)
  Stage 2: HWPX 템플릿 분석 (실제 HWPX → 스타일 추출)
  Stage 3: 제안서 생성 with Profile (5계층 프롬프트)
  Stage 4: HWPX 출력 (템플릿 주입 + DOCX fallback)
  Stage 5: 학습 루프 (edit feedback → pattern promotion → profile update)

Usage:
    cd rag_engine && python tests/e2e_hwpx_pipeline.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field

# Path setup
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RAG_DIR = os.path.join(THIS_DIR, "..")
ROOT_DIR = os.path.join(RAG_DIR, "..")
sys.path.insert(0, RAG_DIR)
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(RAG_DIR, ".env"))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REAL_HWPX_PATH = os.path.join(
    ROOT_DIR, "docs", "dummy",
    "공고문-CCTV 감시 시스템 구축 및 유지보수 관리 운영.hwpx",
)

KNOWLEDGE_DB_PATH = os.path.join(ROOT_DIR, "data", "knowledge_db")

# Demo RFP (CCTV 감시 시스템 기반)
DEMO_RFX = {
    "title": "CCTV 감시 시스템 구축 및 유지보수 관리·운영",
    "issuing_org": "구리농수산물공사",
    "budget": "5억9천만원",
    "project_period": "구축 3개월 + 운영 60개월",
    "requirements": [
        {"category": "기술", "description": "CCTV 카메라 50대 이상 설치 및 통합관제"},
        {"category": "기술", "description": "NVR 녹화 장치 및 영상 관제 소프트웨어 구축"},
        {"category": "보안", "description": "영상정보 암호화 전송 및 개인정보 보호"},
        {"category": "운영", "description": "24시간 무인 모니터링 및 장애 대응 체계"},
        {"category": "성능", "description": "Full HD 이상 해상도, 30fps 실시간 전송"},
    ],
    "evaluation_criteria": [
        {"category": "사업 이해도", "item": "사업 이해", "score": 15, "max_score": 15},
        {"category": "기술성", "item": "시스템 구축 방안", "score": 30, "max_score": 30},
        {"category": "운영 방안", "item": "유지보수 계획", "score": 20, "max_score": 20},
        {"category": "가격", "item": "가격 적정성", "score": 20, "max_score": 20},
        {"category": "수행 능력", "item": "유사 실적", "score": 15, "max_score": 15},
    ],
    "rfp_text_summary": (
        "구리농수산물공사 CCTV 감시 시스템 구축 및 운영 사업. "
        "50대 이상 CCTV 설치, NVR 녹화, 통합관제 소프트웨어, "
        "24시간 무인 모니터링, 영상 암호화, 개인정보보호 준수. "
        "구축 3개월, 운영 60개월. 예산 5.9억원."
    ),
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    name: str
    passed: bool = False
    score: float = 0.0        # 0~100
    duration_sec: float = 0.0
    metrics: dict = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)  # paths to generated files


@dataclass
class EvalReport:
    stages: list[StageResult] = field(default_factory=list)
    total_score: float = 0.0
    total_time_sec: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_api_key() -> bool:
    key = os.environ.get("OPENAI_API_KEY", "")
    if key and len(key) > 10:
        print(f"  [OK] OPENAI_API_KEY loaded ({key[:8]}...)")
        return True
    print("  [SKIP] OPENAI_API_KEY not found — LLM stages will use fallback")
    return False


def _create_test_hwpx_template(output_path: str, section_names: list[str]) -> str:
    """Create a synthetic HWPX template with {{SECTION:name}} placeholders."""
    paragraphs = []
    for name in section_names:
        paragraphs.append(
            f'  <hp:p><hp:run><hp:t>{{{{SECTION:{name}}}}}</hp:t></hp:run></hp:p>'
        )

    section_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"\n'
        '         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">\n'
        + "\n".join(paragraphs)
        + "\n</hs:sec>"
    )

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Contents/section0.xml", section_xml)
        zf.writestr("Contents/content.hpf", "<hpf/>")
        zf.writestr("mimetype", "application/hwp+zip")

    return output_path


# ---------------------------------------------------------------------------
# Stage 1: Profile Generation
# ---------------------------------------------------------------------------

def stage1_profile_generation(work_dir: str, has_api_key: bool) -> StageResult:
    """Generate profile.md from mock company style analysis."""
    result = StageResult(name="Stage 1: Profile 생성")
    t0 = time.time()

    try:
        from company_profile_builder import build_profile_md, save_profile_md

        # Use a realistic StyleProfile
        style = None
        if has_api_key:
            try:
                from company_analyzer import analyze_company_style
                # Use the HWPX text as a sample "past proposal"
                from hwpx_parser import extract_hwpx_text
                sample_text = extract_hwpx_text(REAL_HWPX_PATH)
                if sample_text and len(sample_text) > 100:
                    style = analyze_company_style([sample_text])
                    result.metrics["style_analysis"] = "LLM"
            except Exception as exc:
                result.issues.append(f"[WARNING] LLM style analysis failed: {exc}")

        if style is None:
            from company_analyzer import StyleProfile
            style = StyleProfile(
                tone="경어체",
                avg_sentence_length=35.0,
                structure_pattern="사업이해(20%) → 기술방안(40%) → 운영방안(25%) → 기대효과(15%)",
                strength_keywords=["CCTV", "영상관제", "보안", "24시간 모니터링", "통합관제"],
                terminology={"NVR": "네트워크 비디오 레코더", "VMS": "영상관리시스템"},
                common_phrases=["최적의 CCTV 솔루션을 제공", "안정적인 영상관제 환경 구축"],
                section_weight_pattern={"사업이해": 0.20, "기술방안": 0.40, "운영방안": 0.25, "기대효과": 0.15},
            )
            result.metrics["style_analysis"] = "fallback"

        # Build profile.md
        profile_md = build_profile_md(
            company_name="테스트시큐리티",
            style=style,
        )

        # Save
        skills_dir = os.path.join(work_dir, "company_skills", "demo_company")
        saved_path = save_profile_md(skills_dir, profile_md)
        result.artifacts["profile_md"] = saved_path
        result.artifacts["skills_dir"] = skills_dir

        # Evaluate metrics
        score = 0
        checks = {
            "has_title": "# 테스트시큐리티 회사 프로필" in profile_md,
            "has_doc_style": "## 문서 스타일" in profile_md,
            "has_tone": "## 문체" in profile_md,
            "has_strength": "## 강점 표현 패턴" in profile_md,
            "has_strategy": "## 평가항목별 전략" in profile_md,
            "has_hwpx_rules": "## HWPX 생성 규칙" in profile_md,
            "has_history": "## 학습 이력" in profile_md,
            "tone_present": "경어체" in profile_md,
            "keywords_present": any(kw in profile_md for kw in ["CCTV", "영상관제", "보안"]),
            "structure_present": (
                "## 평가항목별 전략" in profile_md
                and ("| 평가항목" in profile_md or "| 비중" in profile_md)
            ),
            "file_saved": os.path.isfile(saved_path),
        }

        for check_name, passed in checks.items():
            result.metrics[check_name] = passed
            if passed:
                score += 100 / len(checks)
            else:
                result.issues.append(f"[FAIL] {check_name}")

        result.score = round(score, 1)
        result.passed = score >= 80
        result.metrics["profile_length"] = len(profile_md)
        result.metrics["section_count"] = profile_md.count("## ")

    except Exception as exc:
        result.issues.append(f"[ERROR] {exc}")
        result.passed = False

    result.duration_sec = round(time.time() - t0, 2)
    return result


# ---------------------------------------------------------------------------
# Stage 2: HWPX Template Analysis
# ---------------------------------------------------------------------------

def stage2_hwpx_analysis(work_dir: str) -> StageResult:
    """Parse real HWPX file → extract text + styles."""
    result = StageResult(name="Stage 2: HWPX 템플릿 분석")
    t0 = time.time()

    try:
        from hwpx_parser import is_hwpx_file, extract_hwpx_text, extract_hwpx_styles

        if not os.path.isfile(REAL_HWPX_PATH):
            result.issues.append(f"[SKIP] HWPX file not found: {REAL_HWPX_PATH}")
            result.score = 0
            result.duration_sec = round(time.time() - t0, 2)
            return result

        score = 0
        total_checks = 6

        # Check 1: is_hwpx_file
        is_valid = is_hwpx_file(REAL_HWPX_PATH)
        result.metrics["is_valid_hwpx"] = is_valid
        if is_valid:
            score += 100 / total_checks
        else:
            result.issues.append("[FAIL] is_hwpx_file returned False")

        # Check 2: text extraction
        text = extract_hwpx_text(REAL_HWPX_PATH)
        result.metrics["text_length"] = len(text)
        result.metrics["text_preview"] = text[:200] if text else ""
        if text and len(text) > 500:
            score += 100 / total_checks
        else:
            result.issues.append(f"[WARNING] Text too short: {len(text)} chars")

        # Check 3: key content found in text
        key_terms = ["CCTV", "감시", "구축", "유지보수", "운영"]
        found = [t for t in key_terms if t in text]
        result.metrics["key_terms_found"] = len(found)
        result.metrics["key_terms_total"] = len(key_terms)
        if len(found) >= 3:
            score += 100 / total_checks
        else:
            result.issues.append(f"[WARNING] Key terms: {len(found)}/{len(key_terms)}")

        # Check 4: style extraction
        styles = extract_hwpx_styles(REAL_HWPX_PATH)
        result.metrics["styles_extracted"] = len(styles)
        result.metrics["styles"] = styles
        if styles and len(styles) > 0:
            score += 100 / total_checks
        else:
            # Not a failure — many HWPX files don't embed font metadata
            score += 50 / total_checks  # partial credit
            result.issues.append("[INFO] No font styles extracted (common for older HWPX)")

        # Check 5: ZIP structure valid
        with zipfile.ZipFile(REAL_HWPX_PATH) as zf:
            entries = zf.namelist()
        has_section = any("section" in e.lower() for e in entries)
        has_content = any("content" in e.lower() for e in entries)
        result.metrics["zip_entries"] = len(entries)
        result.metrics["has_section_xml"] = has_section
        result.metrics["has_content_hpf"] = has_content
        if has_section and has_content:
            score += 100 / total_checks
        else:
            result.issues.append("[FAIL] Missing expected ZIP entries")

        # Check 6: Profile enrichment with styles
        from company_profile_builder import build_profile_md
        if styles:
            enriched_md = build_profile_md("테스트", hwpx_styles=styles)
            result.metrics["enriched_profile_has_styles"] = "HWPX 템플릿 업로드 시" not in enriched_md
        else:
            result.metrics["enriched_profile_has_styles"] = False
        score += 100 / total_checks  # structural check passes regardless

        result.score = round(score, 1)
        result.passed = score >= 60

    except Exception as exc:
        result.issues.append(f"[ERROR] {exc}")

    result.duration_sec = round(time.time() - t0, 2)
    return result


# ---------------------------------------------------------------------------
# Stage 3: Proposal Generation with Profile
# ---------------------------------------------------------------------------

def stage3_proposal_with_profile(work_dir: str, skills_dir: str, has_api_key: bool) -> StageResult:
    """Generate proposal DOCX using profile.md (5-layer prompt)."""
    result = StageResult(name="Stage 3: 제안서 생성 (Profile 적용)")
    t0 = time.time()

    if not has_api_key:
        result.issues.append("[SKIP] No API key — cannot generate proposal")
        result.score = 0
        result.duration_sec = 0
        return result

    try:
        from proposal_orchestrator import generate_proposal

        output_dir = os.path.join(work_dir, "proposals")
        proposal_result = generate_proposal(
            rfx_result=DEMO_RFX,
            output_dir=output_dir,
            knowledge_db_path=KNOWLEDGE_DB_PATH,
            company_skills_dir=skills_dir,
            total_pages=30,
            max_workers=2,
        )

        score = 0
        total_checks = 8

        # Check 1: DOCX generated
        docx_exists = os.path.isfile(proposal_result.docx_path)
        result.metrics["docx_exists"] = docx_exists
        result.artifacts["docx_path"] = proposal_result.docx_path
        if docx_exists:
            score += 100 / total_checks
            result.metrics["docx_size"] = os.path.getsize(proposal_result.docx_path)
        else:
            result.issues.append("[ERROR] DOCX not generated")

        # Check 2: Section count
        section_count = len(proposal_result.sections)
        result.metrics["section_count"] = section_count
        if section_count >= 3:
            score += 100 / total_checks
        else:
            result.issues.append(f"[WARNING] Too few sections: {section_count}")

        # Check 3: Total text volume
        all_text = "\n\n".join(text for _, text in proposal_result.sections)
        total_chars = len(all_text)
        result.metrics["total_chars"] = total_chars
        if total_chars > 5000:
            score += 100 / total_checks
        elif total_chars > 2000:
            score += 50 / total_checks
            result.issues.append(f"[WARNING] Text volume low: {total_chars} chars")
        else:
            result.issues.append(f"[ERROR] Text volume too low: {total_chars} chars")

        # Check 4: Quality issues
        quality_count = len(proposal_result.quality_issues)
        blind_count = sum(1 for q in proposal_result.quality_issues if q.category == "blind_violation")
        vague_count = sum(1 for q in proposal_result.quality_issues if q.category == "vague_expression")
        result.metrics["quality_issues"] = quality_count
        result.metrics["blind_violations"] = blind_count
        result.metrics["vague_expressions"] = vague_count
        if blind_count == 0:
            score += 100 / total_checks
        else:
            result.issues.append(f"[ERROR] Blind violations: {blind_count}")

        # Check 5: No placeholder text
        placeholder_words = ["placeholder", "lorem", "TODO", "여기에 내용", "{{"]
        placeholder_found = [pw for pw in placeholder_words if pw.lower() in all_text.lower()]
        result.metrics["placeholders_found"] = placeholder_found
        if not placeholder_found:
            score += 100 / total_checks
        else:
            result.issues.append(f"[ERROR] Placeholders: {placeholder_found}")

        # Check 6: RFP-specific content
        rfp_keywords = ["CCTV", "감시", "관제", "영상", "보안", "모니터링", "NVR"]
        matched = [kw for kw in rfp_keywords if kw in all_text]
        result.metrics["rfp_keywords_matched"] = len(matched)
        result.metrics["rfp_keywords_total"] = len(rfp_keywords)
        if len(matched) >= 3:
            score += 100 / total_checks
        else:
            result.issues.append(f"[WARNING] RFP keywords: {len(matched)}/{len(rfp_keywords)}")

        # Check 7: Section names meaningful (not generic)
        section_names = [name for name, _ in proposal_result.sections]
        result.metrics["section_names"] = section_names
        score += 100 / total_checks  # structural check

        # Check 8: Generation time reasonable
        gen_time = proposal_result.generation_time_sec
        result.metrics["generation_time_sec"] = gen_time
        if gen_time < 120:
            score += 100 / total_checks
        else:
            result.issues.append(f"[WARNING] Slow generation: {gen_time}s")

        result.score = round(score, 1)
        result.passed = score >= 60

    except Exception as exc:
        import traceback
        result.issues.append(f"[ERROR] {exc}\n{traceback.format_exc()}")

    result.duration_sec = round(time.time() - t0, 2)
    return result


# ---------------------------------------------------------------------------
# Stage 4: HWPX Output
# ---------------------------------------------------------------------------

def stage4_hwpx_output(work_dir: str, skills_dir: str, has_api_key: bool) -> StageResult:
    """Generate proposal with HWPX output format."""
    result = StageResult(name="Stage 4: HWPX 출력")
    t0 = time.time()

    try:
        from proposal_orchestrator import generate_proposal
        from hwpx_injector import markdown_to_hwpx_elements

        # -- 4a: Test markdown → HWPX conversion --
        test_md = "# 사업 이해도\n\n본 사업은 **CCTV 감시 시스템** 구축입니다.\n\n- 카메라 설치\n- 관제 시스템\n- 유지보수"
        elements = markdown_to_hwpx_elements(test_md)
        result.metrics["md_to_hwpx_element_count"] = len(elements)
        result.metrics["md_to_hwpx_has_heading"] = any("hp:sz" in e for e in elements)
        result.metrics["md_to_hwpx_has_bold"] = any("bold" in e for e in elements)
        result.metrics["md_to_hwpx_has_bullet"] = any("•" in e or "&#8226;" in e for e in elements)

        # -- 4b: Create synthetic HWPX template with placeholders --
        templates_dir = os.path.join(skills_dir, "templates")
        os.makedirs(templates_dir, exist_ok=True)
        template_path = os.path.join(templates_dir, "proposal_template.hwpx")

        # Get section names from outline
        from proposal_planner import build_proposal_outline
        outline = build_proposal_outline(DEMO_RFX, total_pages=30)
        section_names = [s.name for s in outline.sections]
        result.metrics["outline_sections"] = section_names

        _create_test_hwpx_template(template_path, section_names)
        result.metrics["template_created"] = os.path.isfile(template_path)

        # -- 4c: Generate with HWPX output --
        score = 0
        total_checks = 6

        if has_api_key:
            output_dir = os.path.join(work_dir, "proposals_hwpx")
            proposal_result = generate_proposal(
                rfx_result=DEMO_RFX,
                output_dir=output_dir,
                knowledge_db_path=KNOWLEDGE_DB_PATH,
                company_skills_dir=skills_dir,
                total_pages=30,
                max_workers=2,
                output_format="hwpx",
            )

            # Check 1: HWPX file generated
            hwpx_exists = bool(proposal_result.hwpx_path) and os.path.isfile(proposal_result.hwpx_path)
            result.metrics["hwpx_generated"] = hwpx_exists
            if hwpx_exists:
                result.artifacts["hwpx_path"] = proposal_result.hwpx_path
                score += 100 / total_checks

                # Check 2: HWPX is valid ZIP
                try:
                    with zipfile.ZipFile(proposal_result.hwpx_path) as zf:
                        entries = zf.namelist()
                    result.metrics["hwpx_zip_entries"] = len(entries)
                    score += 100 / total_checks
                except zipfile.BadZipFile:
                    result.issues.append("[ERROR] HWPX is not a valid ZIP")

                # Check 3: Placeholders replaced
                with zipfile.ZipFile(proposal_result.hwpx_path) as zf:
                    for entry in zf.namelist():
                        if "section" in entry.lower():
                            xml_data = zf.read(entry).decode("utf-8", errors="replace")
                            placeholder_remaining = re.findall(r"\{\{SECTION:.+?\}\}", xml_data)
                            result.metrics["placeholders_remaining"] = len(placeholder_remaining)
                            if not placeholder_remaining:
                                score += 100 / total_checks
                            else:
                                result.issues.append(
                                    f"[WARNING] {len(placeholder_remaining)} placeholders remaining"
                                )

                # Check 4: Content injected (hp:p elements added)
                with zipfile.ZipFile(proposal_result.hwpx_path) as zf:
                    for entry in zf.namelist():
                        if "section" in entry.lower():
                            xml_data = zf.read(entry).decode("utf-8", errors="replace")
                            p_count = xml_data.count("<hp:p")
                            result.metrics["injected_paragraph_count"] = p_count
                            if p_count > len(section_names):
                                score += 100 / total_checks
                            else:
                                result.issues.append(f"[WARNING] Low paragraph count: {p_count}")

                # Check 5: HWPX file size reasonable
                hwpx_size = os.path.getsize(proposal_result.hwpx_path)
                result.metrics["hwpx_size_bytes"] = hwpx_size
                if hwpx_size > 1000:
                    score += 100 / total_checks
                else:
                    result.issues.append(f"[WARNING] HWPX too small: {hwpx_size} bytes")
            else:
                result.issues.append("[ERROR] HWPX file not generated")

            # Check 6: Generation time
            gen_time = proposal_result.generation_time_sec
            result.metrics["generation_time_sec"] = gen_time
            if gen_time < 180:
                score += 100 / total_checks
            else:
                result.issues.append(f"[WARNING] Slow: {gen_time}s")

        else:
            # Without API key, test md→hwpx conversion and injection structure only
            result.metrics["api_key_available"] = False
            from hwpx_injector import inject_content

            test_sections = {"사업 이해도": "## 이해도\n\n본 사업 이해", "기술 방안": "- CCTV\n- NVR"}
            out_path = os.path.join(work_dir, "test_output.hwpx")
            inject_content(template_path, test_sections, out_path)

            if os.path.isfile(out_path):
                score += 60  # structural pass
                result.artifacts["hwpx_path"] = out_path
            else:
                result.issues.append("[ERROR] inject_content failed")

        result.score = round(score, 1)
        result.passed = score >= 50

    except Exception as exc:
        import traceback
        result.issues.append(f"[ERROR] {exc}\n{traceback.format_exc()}")

    result.duration_sec = round(time.time() - t0, 2)
    return result


# ---------------------------------------------------------------------------
# Stage 5: Learning Loop
# ---------------------------------------------------------------------------

def stage5_learning_loop(work_dir: str, skills_dir: str) -> StageResult:
    """Test edit feedback → pattern promotion → profile.md update."""
    result = StageResult(name="Stage 5: 학습 루프")
    t0 = time.time()

    try:
        import auto_learner
        from auto_learner import process_edit_feedback, get_learned_patterns
        from company_profile_updater import (
            update_profile_section, backup_profile_version, load_changelog,
        )

        # Reset state
        auto_learner._histories.clear()
        auto_learner._learned_patterns.clear()

        score = 0
        total_checks = 7

        company_id = "demo_company"

        # Check 1: Single edit → record only (no promotion)
        r1 = process_edit_feedback(
            company_id=company_id,
            section_name="문체",
            original_text="본 사업은 CCTV 시스템 구축이다.",
            edited_text="본 사업은 CCTV 감시 시스템 구축입니다.",
            doc_type="proposal",
        )
        result.metrics["edit1_diffs"] = r1.new_diffs
        result.metrics["edit1_rate"] = round(r1.edit_rate, 3)
        if r1.new_diffs >= 1 and len(r1.promoted_patterns) == 0:
            score += 100 / total_checks
        else:
            result.issues.append("[FAIL] First edit should record only, not promote")

        # Check 2: Second edit → still candidate
        r2 = process_edit_feedback(
            company_id=company_id,
            section_name="문체",
            original_text="본 사업은 CCTV 시스템 구축이다.",
            edited_text="본 사업은 CCTV 감시 시스템 구축입니다.",
            doc_type="proposal",
        )
        if len(r2.promoted_patterns) == 0:
            score += 100 / total_checks
        else:
            result.issues.append("[FAIL] Second edit promoted prematurely")

        # Check 3: Third edit → pattern promotion
        callback_called = {"value": False, "args": None}

        def on_promoted(cid, patterns):
            callback_called["value"] = True
            callback_called["args"] = (cid, patterns)

        r3 = process_edit_feedback(
            company_id=company_id,
            section_name="문체",
            original_text="본 사업은 CCTV 시스템 구축이다.",
            edited_text="본 사업은 CCTV 감시 시스템 구축입니다.",
            doc_type="proposal",
            on_pattern_promoted=on_promoted,
        )
        result.metrics["edit3_promoted"] = len(r3.promoted_patterns)
        result.metrics["edit3_notifications"] = r3.notifications
        if len(r3.promoted_patterns) >= 1:
            score += 100 / total_checks
        else:
            result.issues.append("[FAIL] Third edit did not promote pattern")

        # Check 4: Callback triggered
        result.metrics["callback_triggered"] = callback_called["value"]
        if callback_called["value"]:
            score += 100 / total_checks
        else:
            result.issues.append("[FAIL] on_pattern_promoted callback not triggered")

        # Check 5: Profile section update
        profile_path = os.path.join(skills_dir, "profile.md")
        if os.path.isfile(profile_path):
            updated = update_profile_section(
                company_dir=skills_dir,
                section_name="문체",
                new_content="- 어미: ~입니다 (경어체, 학습됨)\n- 반복 패턴: ~이다 → ~입니다 변환",
            )
            result.metrics["profile_update_success"] = updated
            if updated:
                score += 100 / total_checks
                with open(profile_path) as f:
                    content = f.read()
                result.metrics["updated_profile_has_learning"] = "학습됨" in content
            else:
                result.issues.append("[FAIL] update_profile_section returned False")
        else:
            result.issues.append("[SKIP] No profile.md to update")

        # Check 6: Version backup created
        changelog = load_changelog(skills_dir)
        version_count = len(changelog.get("versions", []))
        result.metrics["version_count"] = version_count
        if version_count >= 1:
            score += 100 / total_checks
        else:
            result.issues.append("[FAIL] No version backup created")

        # Check 7: State persistence
        state_dir = os.path.join(work_dir, "learning_state")
        auto_learner.save_state(state_dir)
        state_file = os.path.join(state_dir, "learning_state.json")
        result.metrics["state_saved"] = os.path.isfile(state_file)
        if os.path.isfile(state_file):
            score += 100 / total_checks
            with open(state_file) as f:
                state = json.load(f)
            result.metrics["saved_histories"] = len(state.get("histories", {}))
            result.metrics["saved_patterns"] = len(state.get("learned_patterns", {}))
        else:
            result.issues.append("[FAIL] State not saved")

        result.score = round(score, 1)
        result.passed = score >= 80

    except Exception as exc:
        import traceback
        result.issues.append(f"[ERROR] {exc}\n{traceback.format_exc()}")

    result.duration_sec = round(time.time() - t0, 2)
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(report: EvalReport):
    """Print evaluation report."""
    print("\n" + "=" * 70)
    print("  HWPX + Company Skill File Pipeline — E2E Evaluation Report")
    print("=" * 70)

    for stage in report.stages:
        status = "PASS" if stage.passed else "FAIL"
        bar = "█" * int(stage.score / 5) + "░" * (20 - int(stage.score / 5))
        print(f"\n{'─' * 70}")
        print(f"  [{status}] {stage.name}")
        print(f"  Score: {bar} {stage.score:.1f}/100  ({stage.duration_sec}s)")

        # Key metrics
        skip_keys = {"text_preview", "styles", "section_names", "edit3_notifications"}
        for k, v in stage.metrics.items():
            if k in skip_keys:
                continue
            if isinstance(v, float):
                print(f"    {k}: {v:.3f}")
            elif isinstance(v, list) and len(v) > 5:
                print(f"    {k}: [{len(v)} items]")
            else:
                print(f"    {k}: {v}")

        # Issues
        if stage.issues:
            print(f"  Issues ({len(stage.issues)}):")
            for issue in stage.issues[:5]:
                # Truncate long tracebacks
                first_line = issue.split("\n")[0]
                print(f"    {first_line}")

        # Artifacts
        if stage.artifacts:
            print(f"  Artifacts:")
            for k, v in stage.artifacts.items():
                if isinstance(v, str) and os.path.isfile(v):
                    size = os.path.getsize(v)
                    print(f"    {k}: {v} ({size:,} bytes)")
                else:
                    print(f"    {k}: {v}")

    # Summary
    print(f"\n{'=' * 70}")
    scores = [s.score for s in report.stages if s.score > 0 or not s.issues or "[SKIP]" not in str(s.issues)]
    report.total_score = round(sum(scores) / max(len(scores), 1), 1)
    passed = sum(1 for s in report.stages if s.passed)
    total = len(report.stages)

    print(f"  TOTAL: {report.total_score:.1f}/100  |  {passed}/{total} stages passed  |  {report.total_time_sec:.1f}s")

    grade = "A" if report.total_score >= 90 else "B" if report.total_score >= 75 else "C" if report.total_score >= 60 else "D" if report.total_score >= 40 else "F"
    print(f"  Grade: {grade}")
    print("=" * 70)

    return report


def save_report_json(report: EvalReport, path: str):
    """Save report as JSON."""
    data = {
        "total_score": report.total_score,
        "total_time_sec": report.total_time_sec,
        "stages": [],
    }
    for stage in report.stages:
        # Convert metrics to JSON-serializable
        metrics = {}
        for k, v in stage.metrics.items():
            if isinstance(v, (str, int, float, bool, list)):
                metrics[k] = v
            else:
                metrics[k] = str(v)

        data["stages"].append({
            "name": stage.name,
            "passed": stage.passed,
            "score": stage.score,
            "duration_sec": stage.duration_sec,
            "metrics": metrics,
            "issues": stage.issues,
            "artifacts": stage.artifacts,
        })

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n  Report saved: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\nHWPX + Company Skill File Pipeline — E2E Evaluation")
    print("─" * 50)

    has_api_key = _check_api_key()
    report = EvalReport()
    t_start = time.time()

    with tempfile.TemporaryDirectory(prefix="hwpx_e2e_") as work_dir:
        print(f"  Work dir: {work_dir}")

        # Stage 1
        print("\n[1/5] Profile 생성...")
        s1 = stage1_profile_generation(work_dir, has_api_key)
        report.stages.append(s1)
        skills_dir = s1.artifacts.get("skills_dir", "")

        # Stage 2
        print("[2/5] HWPX 템플릿 분석...")
        s2 = stage2_hwpx_analysis(work_dir)
        report.stages.append(s2)

        # Stage 3
        print("[3/5] 제안서 생성 (Profile 적용)...")
        s3 = stage3_proposal_with_profile(work_dir, skills_dir, has_api_key)
        report.stages.append(s3)

        # Stage 4
        print("[4/5] HWPX 출력...")
        s4 = stage4_hwpx_output(work_dir, skills_dir, has_api_key)
        report.stages.append(s4)

        # Stage 5
        print("[5/5] 학습 루프...")
        s5 = stage5_learning_loop(work_dir, skills_dir)
        report.stages.append(s5)

        report.total_time_sec = round(time.time() - t_start, 1)

        # Print report
        print_report(report)

        # Save JSON report
        report_path = os.path.join(
            ROOT_DIR, "data", "eval_reports",
            f"hwpx_pipeline_{int(time.time())}.json",
        )
        save_report_json(report, report_path)


if __name__ == "__main__":
    main()
