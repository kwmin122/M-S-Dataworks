# HWPX 템플릿 + 회사별 Skill File 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 회사별 profile.md(스킬 파일)를 자동 생성하고, HWPX 템플릿에 AI 콘텐츠를 주입하여 회사 양식이 보존된 제안서를 출력한다.

**Architecture:** company_analyzer(기존) + hwpx_parser(신규)로 과거 제안서 분석 → profile.md 생성 → section_writer 5계층 프롬프트에 주입 → hwpx_injector로 HWPX 템플릿에 콘텐츠 주입. 하이브리드 출력(HWPX/DOCX).

**Tech Stack:** python-hwpx (HWPX 읽기/쓰기), lxml (XML 조작), mistune 3.x (마크다운 파싱), 기존 LLM 스택 (OpenAI + call_with_retry)

**Design Doc:** `docs/plans/2026-03-01-hwpx-company-skill-design.md`

---

## Phase A: 프로필 시스템 (profile.md 생성/관리)

### Task A-0: python-hwpx 의존성 추가

**Files:**
- Modify: `rag_engine/requirements.txt`

**Step 1: requirements.txt에 의존성 추가**

```
# rag_engine/requirements.txt에 아래 2줄 추가
lxml>=5.0.0
python-hwpx>=0.3.0
```

**Step 2: 설치 확인**

Run: `cd rag_engine && pip install -r requirements.txt`
Expected: 정상 설치

**Step 3: import 확인**

Run: `cd rag_engine && python -c "from hwpx import HwpxDocument; print('ok')"`
Expected: `ok`

**Step 4: Commit**

```bash
git add rag_engine/requirements.txt
git commit -m "deps: add python-hwpx and lxml for HWPX template support"
```

---

### Task A-1: company_profile_builder.py — profile.md 자동 생성

**Files:**
- Create: `rag_engine/company_profile_builder.py`
- Test: `rag_engine/tests/test_company_profile_builder.py`

**Context:**
- `company_analyzer.py:24` → `analyze_company_style(documents: list[str]) -> StyleProfile`
- `StyleProfile` fields: `tone, avg_sentence_length, structure_pattern, strength_keywords, terminology, common_phrases, section_weight_pattern`
- profile.md 템플릿은 설계문서 섹션 3 참조
- 디렉토리: `data/company_skills/{company_id}/`

**Step 1: 테스트 작성**

```python
# rag_engine/tests/test_company_profile_builder.py
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from company_profile_builder import build_profile_md, load_profile_md, save_profile_md


def test_build_profile_md_from_style():
    """StyleProfile → profile.md 마크다운 변환."""
    from company_analyzer import StyleProfile
    style = StyleProfile(
        tone="경어체",
        avg_sentence_length=35.2,
        strength_keywords=["클라우드", "마이그레이션", "보안"],
        common_phrases=["축적된 노하우를 바탕으로"],
        section_weight_pattern={"사업이해": 0.15, "기술방안": 0.45, "관리방안": 0.20},
    )
    md = build_profile_md(
        company_name="(주)MS솔루션즈",
        style=style,
    )
    assert "# (주)MS솔루션즈 제안서 프로필" in md
    assert "경어체" in md
    assert "35.2" in md
    assert "클라우드" in md
    assert "축적된 노하우" in md
    assert "## 문서 스타일" in md
    assert "## 문체" in md
    assert "## 강점 표현 패턴" in md
    assert "## 평가항목별 전략" in md


def test_build_profile_md_empty_style():
    """빈 StyleProfile도 유효한 md 생성."""
    from company_analyzer import StyleProfile
    md = build_profile_md("테스트기업", StyleProfile())
    assert "# 테스트기업 제안서 프로필" in md
    assert "## 문서 스타일" in md


def test_save_and_load_profile_md(tmp_path):
    """저장 → 로드 라운드트립."""
    content = "# 테스트 프로필\n\n내용"
    company_dir = str(tmp_path / "comp_001")
    save_profile_md(company_dir, content)
    loaded = load_profile_md(company_dir)
    assert loaded == content


def test_load_profile_md_missing(tmp_path):
    """존재하지 않는 프로필은 빈 문자열."""
    loaded = load_profile_md(str(tmp_path / "nonexistent"))
    assert loaded == ""
```

**Step 2: 테스트 실패 확인**

Run: `cd rag_engine && pytest tests/test_company_profile_builder.py -v`
Expected: FAIL (모듈 없음)

**Step 3: 구현**

```python
# rag_engine/company_profile_builder.py
"""Company Profile Builder — past proposals → profile.md generation.

Converts company_analyzer.StyleProfile + optional HWPX style data
into a structured profile.md file that acts as a "skill file" for LLM prompts.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def build_profile_md(
    company_name: str,
    style: Optional[object] = None,
    hwpx_styles: Optional[dict] = None,
) -> str:
    """Build profile.md markdown from StyleProfile + optional HWPX styles.

    Args:
        company_name: Company name for the profile header.
        style: StyleProfile from company_analyzer (or None).
        hwpx_styles: Dict of HWPX-extracted style info (Phase B, optional).

    Returns:
        Complete profile.md content as string.
    """
    sections: list[str] = []
    sections.append(f"# {company_name} 제안서 프로필\n")

    # --- 문서 스타일 ---
    doc_style_lines = []
    if hwpx_styles:
        if hwpx_styles.get("body_font"):
            doc_style_lines.append(f"- 본문 폰트: {hwpx_styles['body_font']}")
        if hwpx_styles.get("heading_font"):
            doc_style_lines.append(f"- 제목 폰트: {hwpx_styles['heading_font']}")
        if hwpx_styles.get("line_spacing"):
            doc_style_lines.append(f"- 줄간격: {hwpx_styles['line_spacing']}")
        if hwpx_styles.get("margins"):
            doc_style_lines.append(f"- 여백: {hwpx_styles['margins']}")
    if not doc_style_lines:
        doc_style_lines.append("- (HWPX 템플릿 업로드 시 자동 채움)")
    sections.append("## 문서 스타일\n" + "\n".join(doc_style_lines))

    # --- 문체 ---
    tone_lines = []
    if style:
        tone = getattr(style, "tone", "혼합")
        avg_len = getattr(style, "avg_sentence_length", 0.0)
        tone_lines.append(f"- 어미: ~{'합니다 (경어체)' if tone == '경어체' else '이다 (격식체)' if tone == '격식체' else '혼합'}")
        if avg_len > 0:
            tone_lines.append(f"- 평균 문장 길이: {avg_len}자")
        common = getattr(style, "common_phrases", [])
        if common:
            tone_lines.append(f"- 빈출 표현: {', '.join(common[:5])}")
    if not tone_lines:
        tone_lines.append("- (과거 제안서 분석 시 자동 채움)")
    sections.append("## 문체\n" + "\n".join(tone_lines))

    # --- 강점 표현 패턴 ---
    strength_lines = []
    if style:
        keywords = getattr(style, "strength_keywords", [])
        if keywords:
            strength_lines.append(f"- 핵심 키워드: {', '.join(keywords[:10])}")
            strength_lines.append("- (반복 사용 시 자동 패턴 추출)")
    if not strength_lines:
        strength_lines.append("- (과거 제안서 분석 시 자동 채움)")
    sections.append("## 강점 표현 패턴\n" + "\n".join(strength_lines))

    # --- 평가항목별 전략 ---
    strategy_lines = []
    if style:
        weights = getattr(style, "section_weight_pattern", {})
        if weights:
            for name, weight in sorted(weights.items(), key=lambda x: -x[1]):
                pct = f"{weight:.0%}"
                strategy_lines.append(f"- {name} ({pct}): (전략 미설정 — 학습 후 자동 채움)")
    if not strategy_lines:
        strategy_lines.extend([
            "- 기술이해도: (학습 후 자동 채움)",
            "- 수행방법론: (학습 후 자동 채움)",
            "- 프로젝트관리: (학습 후 자동 채움)",
        ])
    sections.append("## 평가항목별 전략\n" + "\n".join(strategy_lines))

    # --- HWPX 생성 규칙 ---
    hwpx_lines = []
    if hwpx_styles:
        if hwpx_styles.get("header_text"):
            hwpx_lines.append(f"- 머리글: {hwpx_styles['header_text']}")
        if hwpx_styles.get("footer_text"):
            hwpx_lines.append(f"- 꼬리글: {hwpx_styles['footer_text']}")
        if hwpx_styles.get("page_number_format"):
            hwpx_lines.append(f"- 페이지 번호: {hwpx_styles['page_number_format']}")
    if not hwpx_lines:
        hwpx_lines.append("- (HWPX 템플릿 업로드 시 자동 채움)")
    sections.append("## HWPX 생성 규칙\n" + "\n".join(hwpx_lines))

    # --- 학습 이력 ---
    from datetime import date
    today = date.today().isoformat()
    sections.append(f"## 학습 이력\n- {today}: 초기 프로필 생성")

    return "\n\n".join(sections) + "\n"


def save_profile_md(company_dir: str, content: str) -> str:
    """Save profile.md to company directory.

    Args:
        company_dir: Path to company_skills/{company_id}/ directory.
        content: profile.md content string.

    Returns:
        Absolute path to saved profile.md.
    """
    os.makedirs(company_dir, exist_ok=True)
    path = os.path.join(company_dir, "profile.md")
    # Atomic write
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)
    return path


def load_profile_md(company_dir: str) -> str:
    """Load profile.md from company directory.

    Returns:
        profile.md content string, or empty string if not found.
    """
    path = os.path.join(company_dir, "profile.md")
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
```

**Step 4: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_company_profile_builder.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add rag_engine/company_profile_builder.py rag_engine/tests/test_company_profile_builder.py
git commit -m "feat: add company_profile_builder for profile.md generation"
```

---

### Task A-2: section_writer.py — 5계층 프롬프트 (Profile 계층 추가)

**Files:**
- Modify: `rag_engine/section_writer.py:22-70` (`_assemble_prompt`)
- Test: `rag_engine/tests/test_section_writer.py`

**Context:**
- 현재 4계층: Layer 1 (지식) → Layer 2 (company_context) → RFP → Task
- 추가: profile.md 내용을 Layer 2와 RFP 사이에 주입 (Profile 계층)
- `write_section()` 시그니처에 `profile_md: str = ""` 파라미터 추가

**Step 1: 테스트 추가**

```python
# test_section_writer.py에 추가
def test_write_section_with_profile_md():
    """profile_md가 프롬프트에 주입되는지 확인."""
    from unittest.mock import patch
    from knowledge_models import ProposalSection

    section = ProposalSection(
        name="기술 방안",
        evaluation_item="기술이해도",
        max_score=20,
        weight=0.25,
    )
    profile_md = "## 문체\n- 어미: ~합니다 (경어체)\n- 핵심 키워드: 클라우드, 보안"

    with patch("section_writer._call_llm_for_section") as mock_llm:
        mock_llm.return_value = "## 기술 방안\n\n내용입니다."
        from section_writer import write_section
        result = write_section(
            section=section,
            rfp_context="사업명: 테스트",
            knowledge=[],
            company_context="",
            profile_md=profile_md,
        )
        # profile_md가 프롬프트에 포함되었는지 확인
        called_prompt = mock_llm.call_args[0][0]
        assert "회사 제안서 프로필" in called_prompt
        assert "경어체" in called_prompt
        assert "클라우드" in called_prompt


def test_write_section_without_profile_md():
    """profile_md 없이도 기존과 동일하게 동작."""
    from unittest.mock import patch
    from knowledge_models import ProposalSection

    section = ProposalSection(
        name="사업 이해",
        evaluation_item="사업이해도",
        max_score=15,
        weight=0.15,
    )

    with patch("section_writer._call_llm_for_section") as mock_llm:
        mock_llm.return_value = "## 사업 이해\n\n내용입니다."
        from section_writer import write_section
        result = write_section(
            section=section,
            rfp_context="사업명: 테스트",
            knowledge=[],
        )
        assert result == "## 사업 이해\n\n내용입니다."
        # profile 관련 텍스트 없음
        called_prompt = mock_llm.call_args[0][0]
        assert "회사 제안서 프로필" not in called_prompt
```

**Step 2: 테스트 실패 확인**

Run: `cd rag_engine && pytest tests/test_section_writer.py::test_write_section_with_profile_md -v`
Expected: FAIL (profile_md 파라미터 없음)

**Step 3: section_writer.py 수정**

`_assemble_prompt()`에 `profile_md` 파라미터 추가, Layer 2와 RFP 사이에 주입:

```python
# section_writer.py:22 — _assemble_prompt 시그니처 변경
def _assemble_prompt(
    section: ProposalSection,
    knowledge: list[KnowledgeUnit],
    rfp_context: str,
    company_context: str = "",
    profile_md: str = "",
) -> str:
```

Layer 2 블록 (line 51-53) 뒤에 Profile 계층 추가:

```python
    # Profile — company skill file (profile.md)
    if profile_md:
        parts.append(f"## 이 회사의 제안서 프로필 (반드시 준수):\n{profile_md}")
```

`write_section()` 시그니처에도 `profile_md` 추가:

```python
# section_writer.py:94
def write_section(
    section: ProposalSection,
    rfp_context: str,
    knowledge: list[KnowledgeUnit],
    company_context: str = "",
    profile_md: str = "",
    api_key: Optional[str] = None,
) -> str:
    """Generate one proposal section with Layer 1 knowledge + profile injection."""
    prompt = _assemble_prompt(section, knowledge, rfp_context, company_context, profile_md)
    return _call_llm_for_section(prompt, api_key)
```

**Step 4: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_section_writer.py -v`
Expected: ALL passed (기존 + 신규 2개)

**Step 5: Commit**

```bash
git add rag_engine/section_writer.py rag_engine/tests/test_section_writer.py
git commit -m "feat: add profile_md layer to section_writer 5-layer prompt"
```

---

### Task A-3: proposal_orchestrator.py — profile.md 로드 + 전달

**Files:**
- Modify: `rag_engine/proposal_orchestrator.py:33-43` (`generate_proposal` 시그니처)
- Test: `rag_engine/tests/test_proposal_orchestrator.py`

**Context:**
- `generate_proposal()`에 `company_skills_dir: str = ""` 파라미터 추가
- company_skills_dir이 있으면 `load_profile_md()` → `write_section(profile_md=...)` 전달
- 기존 company_context 흐름은 그대로 유지

**Step 1: 테스트 추가**

```python
# test_proposal_orchestrator.py에 추가
def test_generate_proposal_with_profile_md(tmp_path):
    """company_skills_dir 지정 시 profile.md가 section_writer에 전달."""
    from unittest.mock import patch, MagicMock, call

    # profile.md 생성
    skills_dir = str(tmp_path / "skills" / "comp_001")
    os.makedirs(skills_dir, exist_ok=True)
    with open(os.path.join(skills_dir, "profile.md"), "w") as f:
        f.write("## 문체\n- 어미: ~합니다")

    rfx = {"title": "테스트 사업", "issuing_org": "기관"}
    mock_kb = MagicMock()
    mock_kb.search.return_value = []

    with patch("proposal_orchestrator.KnowledgeDB", return_value=mock_kb), \
         patch("proposal_orchestrator.write_section") as mock_write, \
         patch("proposal_orchestrator.build_proposal_outline") as mock_outline, \
         patch("proposal_orchestrator.assemble_docx", return_value=str(tmp_path / "out.docx")):
        from knowledge_models import ProposalSection, ProposalOutline
        mock_outline.return_value = ProposalOutline(
            title="테스트",
            issuing_org="기관",
            sections=[ProposalSection(name="개요", evaluation_item="이해도", max_score=10, weight=0.1)],
        )
        mock_write.return_value = "내용"

        from proposal_orchestrator import generate_proposal
        result = generate_proposal(
            rfx_result=rfx,
            output_dir=str(tmp_path),
            knowledge_db_path=str(tmp_path / "kb"),
            company_skills_dir=skills_dir,
        )

        # write_section이 profile_md 인자와 함께 호출됐는지 확인
        assert mock_write.called
        _, kwargs = mock_write.call_args
        assert "합니다" in kwargs.get("profile_md", "")
```

**Step 2: 테스트 실패 확인**

Run: `cd rag_engine && pytest tests/test_proposal_orchestrator.py::test_generate_proposal_with_profile_md -v`
Expected: FAIL

**Step 3: proposal_orchestrator.py 수정**

```python
# proposal_orchestrator.py:33 — 시그니처에 company_skills_dir 추가
def generate_proposal(
    rfx_result: dict[str, Any],
    output_dir: str = "./data/proposals",
    knowledge_db_path: str = "./data/knowledge_db",
    company_context: str = "",
    company_name: Optional[str] = None,
    company_db_path: str = "./data/company_db",
    company_skills_dir: str = "",        # ← 추가
    total_pages: int = 50,
    api_key: Optional[str] = None,
    max_workers: int = 3,
) -> ProposalResult:
```

section writing 전에 profile 로드:

```python
    # 3.5. Load profile.md if available
    profile_md = ""
    if company_skills_dir:
        try:
            from company_profile_builder import load_profile_md
            profile_md = load_profile_md(company_skills_dir)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).debug("Profile load skipped: %s", exc)
```

`_write_one` 내부에서 `profile_md` 전달:

```python
    def _write_one(section):
        knowledge = kb.search(
            f"{section.name} {section.evaluation_item}",
            top_k=10,
        )
        text = write_section(
            section=section,
            rfp_context=rfp_context,
            knowledge=knowledge,
            company_context=company_context,
            profile_md=profile_md,        # ← 추가
            api_key=api_key,
        )
        return (section.name, text)
```

**Step 4: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_proposal_orchestrator.py -v`
Expected: ALL passed

**Step 5: Commit**

```bash
git add rag_engine/proposal_orchestrator.py rag_engine/tests/test_proposal_orchestrator.py
git commit -m "feat: pass profile.md through proposal_orchestrator to section_writer"
```

---

### Task A-4: profile.md CRUD API 엔드포인트

**Files:**
- Modify: `rag_engine/main.py` (기존 company-db 엔드포인트 아래에 추가)
- Test: `rag_engine/tests/test_proposal_api.py` (또는 별도 `test_profile_api.py`)

**Context:**
- 기존 `/api/company-db/analyze-style` (main.py:775) 확장
- 새 엔드포인트:
  - `POST /api/company-profile/generate` — 과거 제안서 텍스트 → profile.md 생성
  - `GET /api/company-profile` — 현재 profile.md 조회
  - `PUT /api/company-profile` — profile.md 수정
- company_skills 기본 경로: `data/company_skills/default/`

**Step 1: 테스트 작성**

```python
# rag_engine/tests/test_profile_api.py
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_generate_profile_endpoint():
    """POST /api/company-profile/generate → profile.md 생성."""
    with patch("main._get_company_skills_dir", return_value="/tmp/test_skills"), \
         patch("company_profile_builder.save_profile_md") as mock_save, \
         patch("company_analyzer.analyze_company_style") as mock_analyze:
        from company_analyzer import StyleProfile
        mock_analyze.return_value = StyleProfile(tone="경어체", avg_sentence_length=30.0)
        mock_save.return_value = "/tmp/test_skills/profile.md"

        resp = client.post("/api/company-profile/generate", json={
            "company_name": "테스트기업",
            "documents": ["본 사업은 클라우드 전환을 위한 프로젝트입니다."],
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "profile_md" in data


def test_get_profile_endpoint():
    """GET /api/company-profile → 현재 profile.md 조회."""
    with patch("main._get_company_skills_dir", return_value="/tmp/test_skills"), \
         patch("company_profile_builder.load_profile_md", return_value="# 테스트 프로필"):
        resp = client.get("/api/company-profile")
    assert resp.status_code == 200
    assert "테스트 프로필" in resp.json()["profile_md"]


def test_get_profile_empty():
    """프로필 없으면 빈 문자열."""
    with patch("main._get_company_skills_dir", return_value="/tmp/nonexist"), \
         patch("company_profile_builder.load_profile_md", return_value=""):
        resp = client.get("/api/company-profile")
    assert resp.status_code == 200
    assert resp.json()["profile_md"] == ""


def test_update_profile_endpoint():
    """PUT /api/company-profile → profile.md 수정."""
    with patch("main._get_company_skills_dir", return_value="/tmp/test_skills"), \
         patch("company_profile_builder.save_profile_md") as mock_save:
        mock_save.return_value = "/tmp/test_skills/profile.md"
        resp = client.put("/api/company-profile", json={
            "profile_md": "# 수정된 프로필\n\n내용",
        })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
```

**Step 2: 테스트 실패 확인**

Run: `cd rag_engine && pytest tests/test_profile_api.py -v`
Expected: FAIL (엔드포인트 없음)

**Step 3: main.py에 엔드포인트 추가**

```python
# main.py — company-db/analyze-style 엔드포인트 아래 (~line 798)

# ---------------------------------------------------------------------------
# Company Profile (profile.md) Management
# ---------------------------------------------------------------------------

def _get_company_skills_dir(company_id: str = "default") -> str:
    """Get company skills directory path."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "company_skills")
    return os.path.join(base, company_id)


class GenerateProfileRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=100)
    documents: list[str] = Field(min_length=1, max_length=20)


class UpdateProfileRequest(BaseModel):
    profile_md: str = Field(min_length=1, max_length=50000)


@app.post("/api/company-profile/generate")
async def generate_company_profile(req: GenerateProfileRequest):
    """Analyze past proposals and generate profile.md."""
    from company_analyzer import analyze_company_style
    from company_profile_builder import build_profile_md, save_profile_md

    truncated = [doc[:_MAX_DOC_CHARS] for doc in req.documents]
    style = await asyncio.to_thread(analyze_company_style, truncated)
    profile_md = build_profile_md(company_name=req.company_name, style=style)

    skills_dir = _get_company_skills_dir()
    save_profile_md(skills_dir, profile_md)

    return {"ok": True, "profile_md": profile_md}


@app.get("/api/company-profile")
async def get_company_profile():
    """Get current profile.md content."""
    from company_profile_builder import load_profile_md
    skills_dir = _get_company_skills_dir()
    content = load_profile_md(skills_dir)
    return {"profile_md": content}


@app.put("/api/company-profile")
async def update_company_profile(req: UpdateProfileRequest):
    """Update profile.md content directly."""
    from company_profile_builder import save_profile_md
    skills_dir = _get_company_skills_dir()
    save_profile_md(skills_dir, req.profile_md)
    return {"ok": True}
```

**Step 4: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_profile_api.py -v`
Expected: 4 passed

**Step 5: 전체 기존 테스트 회귀 확인**

Run: `cd rag_engine && pytest -q`
Expected: 기존 160+ 테스트 + 신규 모두 통과

**Step 6: Commit**

```bash
git add rag_engine/main.py rag_engine/tests/test_profile_api.py
git commit -m "feat: add company profile CRUD API endpoints"
```

---

### Task A-5: generate-proposal-v2에 profile 연동

**Files:**
- Modify: `rag_engine/main.py:301` (`/api/generate-proposal-v2` 엔드포인트)

**Context:**
- 기존 엔드포인트가 `generate_proposal()` 호출 시 `company_skills_dir` 전달하도록 수정
- profile.md가 있으면 자동으로 section_writer에 주입됨

**Step 1: 테스트 추가**

```python
# test_profile_api.py에 추가
def test_generate_proposal_v2_uses_profile(tmp_path):
    """generate-proposal-v2 호출 시 profile.md가 자동 로드."""
    with patch("main._get_company_skills_dir") as mock_dir, \
         patch("proposal_orchestrator.generate_proposal") as mock_gen:
        mock_dir.return_value = str(tmp_path)
        from proposal_orchestrator import ProposalResult
        from knowledge_models import ProposalOutline
        mock_gen.return_value = ProposalResult(
            docx_path="/tmp/test.docx",
            sections=[("개요", "내용")],
            outline=ProposalOutline(title="t", issuing_org="o", sections=[]),
        )

        resp = client.post("/api/generate-proposal-v2", json={
            "rfx_result": {"title": "테스트", "issuing_org": "기관"},
        })

    assert resp.status_code == 200
    # generate_proposal이 company_skills_dir과 함께 호출됐는지
    _, kwargs = mock_gen.call_args
    assert "company_skills_dir" in kwargs
```

**Step 2: main.py의 generate-proposal-v2 엔드포인트에서 company_skills_dir 전달**

```python
# /api/generate-proposal-v2 핸들러 내부, generate_proposal() 호출 부분에 추가:
    company_skills_dir = _get_company_skills_dir()
    # ... generate_proposal(..., company_skills_dir=company_skills_dir)
```

**Step 3: 테스트 통과 + 전체 회귀**

Run: `cd rag_engine && pytest tests/test_profile_api.py tests/test_proposal_api.py -v`
Expected: ALL passed

**Step 4: Commit**

```bash
git add rag_engine/main.py rag_engine/tests/test_profile_api.py
git commit -m "feat: connect profile.md to generate-proposal-v2 endpoint"
```

---

## Phase B: HWPX 엔진 (읽기/쓰기)

### Task B-1: hwpx_parser.py — HWPX 텍스트 추출 + 구조 분석

**Files:**
- Create: `rag_engine/hwpx_parser.py`
- Test: `rag_engine/tests/test_hwpx_parser.py`

**Context:**
- python-hwpx 의존성 (Task A-0에서 설치)
- 기존 `hwp_parser.py`는 HWP 5.x 전용. HWPX는 별도 모듈.
- 두 가지 역할: (1) 텍스트 추출 (과거 제안서 분석용), (2) 스타일 추출 (profile.md 보강용)
- HWPX는 ZIP 파일: Contents/section*.xml에 본문, settings.xml에 스타일

**Step 1: 테스트 작성**

```python
# rag_engine/tests/test_hwpx_parser.py
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from hwpx_parser import extract_hwpx_text, extract_hwpx_styles, is_hwpx_file


def test_is_hwpx_file_valid(tmp_path):
    """HWPX (ZIP with Contents/) 파일 감지."""
    import zipfile
    hwpx_path = str(tmp_path / "test.hwpx")
    with zipfile.ZipFile(hwpx_path, "w") as zf:
        zf.writestr("Contents/section0.xml", "<sec/>")
        zf.writestr("Contents/content.hpf", "<hpf/>")
    assert is_hwpx_file(hwpx_path) is True


def test_is_hwpx_file_invalid(tmp_path):
    """비 HWPX 파일 거부."""
    txt_path = str(tmp_path / "test.txt")
    with open(txt_path, "w") as f:
        f.write("hello")
    assert is_hwpx_file(txt_path) is False


def test_extract_text_from_hwpx(tmp_path):
    """HWPX section XML에서 텍스트 추출."""
    import zipfile
    section_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p>
    <hp:run>
      <hp:t>본 사업은 클라우드 전환입니다.</hp:t>
    </hp:run>
  </hp:p>
  <hp:p>
    <hp:run>
      <hp:t>두 번째 문단입니다.</hp:t>
    </hp:run>
  </hp:p>
</hs:sec>"""
    hwpx_path = str(tmp_path / "test.hwpx")
    with zipfile.ZipFile(hwpx_path, "w") as zf:
        zf.writestr("Contents/section0.xml", section_xml)
        zf.writestr("Contents/content.hpf", "<hpf/>")

    text = extract_hwpx_text(hwpx_path)
    assert "클라우드 전환" in text
    assert "두 번째 문단" in text


def test_extract_text_empty_hwpx(tmp_path):
    """빈 HWPX는 빈 문자열."""
    import zipfile
    hwpx_path = str(tmp_path / "empty.hwpx")
    with zipfile.ZipFile(hwpx_path, "w") as zf:
        zf.writestr("Contents/content.hpf", "<hpf/>")
    text = extract_hwpx_text(hwpx_path)
    assert text == ""


def test_extract_styles_from_hwpx(tmp_path):
    """HWPX에서 스타일 정보 추출."""
    import zipfile
    section_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p>
    <hp:run>
      <hp:rPr>
        <hp:fontRef hangul="함초롬바탕" latin="Times New Roman"/>
        <hp:sz val="2200"/>
      </hp:rPr>
      <hp:t>본문</hp:t>
    </hp:run>
  </hp:p>
</hs:sec>"""
    hwpx_path = str(tmp_path / "styled.hwpx")
    with zipfile.ZipFile(hwpx_path, "w") as zf:
        zf.writestr("Contents/section0.xml", section_xml)
        zf.writestr("Contents/content.hpf", "<hpf/>")

    styles = extract_hwpx_styles(hwpx_path)
    assert isinstance(styles, dict)
    # 폰트 정보가 추출되어야 함
    assert "body_font" in styles or "fonts" in styles
```

**Step 2: 테스트 실패 확인**

Run: `cd rag_engine && pytest tests/test_hwpx_parser.py -v`
Expected: FAIL

**Step 3: 구현**

```python
# rag_engine/hwpx_parser.py
"""HWPX Parser — extract text and styles from HWPX (한글 XML) files.

HWPX is a ZIP archive containing XML files:
- Contents/section*.xml: Document body (paragraphs, tables, images)
- Contents/content.hpf: Document metadata
- settings.xml: Page settings (margins, line spacing)

Uses zipfile + lxml for reliable XML parsing with namespace support.
"""
from __future__ import annotations

import logging
import os
import zipfile
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# HWPX XML namespaces
_NS = {
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}


def is_hwpx_file(path: str) -> bool:
    """Check if file is a valid HWPX archive."""
    if not os.path.isfile(path):
        return False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            return any(n.startswith("Contents/") for n in names)
    except (zipfile.BadZipFile, OSError):
        return False


def extract_hwpx_text(path: str) -> str:
    """Extract all text from HWPX file.

    Parses each Contents/section*.xml and extracts text from
    hp:t elements within hp:run elements.

    Returns:
        Concatenated text with newlines between paragraphs.
        Empty string if parsing fails.
    """
    if not is_hwpx_file(path):
        logger.warning("Not a valid HWPX file: %s", path)
        return ""

    try:
        from lxml import etree
    except ImportError:
        logger.error("lxml not installed. Run: pip install lxml")
        return ""

    paragraphs: list[str] = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            section_files = sorted(
                n for n in zf.namelist()
                if n.startswith("Contents/section") and n.endswith(".xml")
            )
            for section_file in section_files:
                xml_bytes = zf.read(section_file)
                root = etree.fromstring(xml_bytes)
                # Find all hp:t text elements
                for t_elem in root.iter("{%s}t" % _NS["hp"]):
                    text = t_elem.text
                    if text and text.strip():
                        paragraphs.append(text.strip())
    except Exception as exc:
        logger.error("HWPX text extraction failed: %s", exc)
        return ""

    return "\n".join(paragraphs)


def extract_hwpx_styles(path: str) -> dict:
    """Extract style information from HWPX file.

    Analyzes font references, sizes, and page settings.

    Returns:
        Dict with keys: body_font, heading_font, fonts, font_sizes, etc.
        Empty dict if parsing fails.
    """
    if not is_hwpx_file(path):
        return {}

    try:
        from lxml import etree
    except ImportError:
        return {}

    fonts: Counter = Counter()
    font_sizes: Counter = Counter()
    result: dict = {}

    try:
        with zipfile.ZipFile(path, "r") as zf:
            section_files = sorted(
                n for n in zf.namelist()
                if n.startswith("Contents/section") and n.endswith(".xml")
            )
            for section_file in section_files:
                xml_bytes = zf.read(section_file)
                root = etree.fromstring(xml_bytes)

                # Extract font references
                for font_ref in root.iter("{%s}fontRef" % _NS["hp"]):
                    hangul = font_ref.get("hangul", "")
                    if hangul:
                        fonts[hangul] += 1

                # Extract font sizes
                for sz in root.iter("{%s}sz" % _NS["hp"]):
                    val = sz.get("val", "")
                    if val:
                        try:
                            # HWPX stores size in 1/100 pt
                            pt = int(val) / 100
                            font_sizes[pt] += 1
                        except ValueError:
                            pass

        # Determine primary body font (most frequent)
        if fonts:
            result["body_font"] = fonts.most_common(1)[0][0]
            result["fonts"] = dict(fonts.most_common(5))

        # Determine body/heading sizes
        if font_sizes:
            sorted_sizes = font_sizes.most_common()
            result["body_font_size"] = sorted_sizes[0][0]
            if len(sorted_sizes) > 1:
                # Largest font is likely heading
                all_sizes = [s for s, _ in sorted_sizes]
                result["heading_font_size"] = max(all_sizes)
            result["font_sizes"] = dict(sorted_sizes[:5])

    except Exception as exc:
        logger.error("HWPX style extraction failed: %s", exc)

    return result
```

**Step 4: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_hwpx_parser.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add rag_engine/hwpx_parser.py rag_engine/tests/test_hwpx_parser.py
git commit -m "feat: add hwpx_parser for text and style extraction"
```

---

### Task B-2: hwpx_injector.py — HWPX 템플릿에 콘텐츠 주입

**Files:**
- Create: `rag_engine/hwpx_injector.py`
- Test: `rag_engine/tests/test_hwpx_injector.py`

**Context:**
- HWPX 템플릿의 section*.xml에 마크다운 콘텐츠를 XML로 변환하여 주입
- mistune 3.x AST를 사용하여 마크다운 파싱 (document_assembler.py 패턴 재사용)
- 플레이스홀더 마커: `{{SECTION:섹션명}}` 형태로 템플릿에 표시

**마크다운 → HWPX XML 변환 매핑 테이블:**

| 마크다운 | HWPX XML |
|---------|----------|
| `# 제목` | `<hp:p><hp:run><hp:rPr styleRef="Heading1"/><hp:t>제목</hp:t></hp:run></hp:p>` |
| `## 소제목` | `<hp:p><hp:run><hp:rPr styleRef="Heading2"/><hp:t>소제목</hp:t></hp:run></hp:p>` |
| 본문 텍스트 | `<hp:p><hp:run><hp:t>본문</hp:t></hp:run></hp:p>` |
| `**볼드**` | `<hp:run><hp:rPr bold="true"/><hp:t>볼드</hp:t></hp:run>` |
| `*이탤릭*` | `<hp:run><hp:rPr italic="true"/><hp:t>이탤릭</hp:t></hp:run>` |
| `- 불렛` | `<hp:p><hp:lPr><hp:bullet/></hp:lPr><hp:run><hp:t>불렛</hp:t></hp:run></hp:p>` |
| `1. 번호` | `<hp:p><hp:lPr><hp:numbering/></hp:lPr><hp:run><hp:t>번호</hp:t></hp:run></hp:p>` |
| 표 `|a|b|` | `<hp:tbl><hp:tr><hp:tc><hp:p>...</hp:p></hp:tc></hp:tr></hp:tbl>` |

**Step 1: 테스트 작성**

```python
# rag_engine/tests/test_hwpx_injector.py
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import zipfile
from hwpx_injector import inject_content, markdown_to_hwpx_elements


def _make_template(tmp_path, placeholder_text="{{SECTION:개요}}"):
    """테스트용 HWPX 템플릿 생성."""
    section_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p>
    <hp:run>
      <hp:t>표지 내용</hp:t>
    </hp:run>
  </hp:p>
  <hp:p>
    <hp:run>
      <hp:t>{placeholder_text}</hp:t>
    </hp:run>
  </hp:p>
  <hp:p>
    <hp:run>
      <hp:t>{{{{SECTION:기술방안}}}}</hp:t>
    </hp:run>
  </hp:p>
</hs:sec>"""
    path = str(tmp_path / "template.hwpx")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Contents/section0.xml", section_xml)
        zf.writestr("Contents/content.hpf", "<hpf/>")
    return path


def test_markdown_to_hwpx_heading():
    """마크다운 제목 → HWPX heading 변환."""
    elements = markdown_to_hwpx_elements("# 제안 개요\n\n본문입니다.")
    # 최소 2개 요소 (heading + paragraph)
    assert len(elements) >= 2


def test_markdown_to_hwpx_bold():
    """**볼드** → bold run 변환."""
    elements = markdown_to_hwpx_elements("이것은 **중요한** 텍스트입니다.")
    xml_str = "\n".join(elements)
    assert "bold" in xml_str.lower() or "Bold" in xml_str


def test_markdown_to_hwpx_bullet():
    """- 불렛 → bullet paragraph 변환."""
    elements = markdown_to_hwpx_elements("- 항목1\n- 항목2\n- 항목3")
    assert len(elements) >= 3


def test_inject_content_replaces_placeholder(tmp_path):
    """템플릿의 {{SECTION:개요}}를 실제 콘텐츠로 교체."""
    template_path = _make_template(tmp_path)
    output_path = str(tmp_path / "output.hwpx")

    sections = {
        "개요": "## 제안 개요\n\n본 사업은 **클라우드 전환** 프로젝트입니다.",
        "기술방안": "## 기술적 접근\n\n- React\n- FastAPI\n- PostgreSQL",
    }

    result = inject_content(
        template_path=template_path,
        sections=sections,
        output_path=output_path,
    )
    assert os.path.exists(result)
    assert result.endswith(".hwpx")

    # 출력 HWPX에서 텍스트 확인
    from hwpx_parser import extract_hwpx_text
    text = extract_hwpx_text(result)
    assert "클라우드 전환" in text
    assert "{{SECTION:" not in text  # 플레이스홀더 제거됨


def test_inject_content_preserves_non_placeholder(tmp_path):
    """플레이스홀더 아닌 기존 콘텐츠는 보존."""
    template_path = _make_template(tmp_path)
    output_path = str(tmp_path / "output.hwpx")

    sections = {"개요": "내용", "기술방안": "기술 내용"}
    inject_content(template_path, sections, output_path)

    from hwpx_parser import extract_hwpx_text
    text = extract_hwpx_text(output_path)
    assert "표지 내용" in text


def test_inject_content_missing_section(tmp_path):
    """없는 섹션은 플레이스홀더 그대로 유지."""
    template_path = _make_template(tmp_path)
    output_path = str(tmp_path / "output.hwpx")

    # 개요만 제공, 기술방안은 미제공
    sections = {"개요": "개요 내용"}
    inject_content(template_path, sections, output_path)

    from hwpx_parser import extract_hwpx_text
    text = extract_hwpx_text(output_path)
    assert "개요 내용" in text
```

**Step 2: 테스트 실패 확인**

Run: `cd rag_engine && pytest tests/test_hwpx_injector.py -v`
Expected: FAIL

**Step 3: 구현**

```python
# rag_engine/hwpx_injector.py
"""HWPX Injector — inject markdown content into HWPX templates.

Replaces {{SECTION:섹션명}} placeholders in HWPX templates with
AI-generated content, converting markdown to HWPX XML elements.

Uses mistune 3.x AST for markdown parsing (same as document_assembler.py).
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import zipfile
from typing import Optional

logger = logging.getLogger(__name__)

# HWPX XML namespace prefix
_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"

_PLACEHOLDER_RE = re.compile(r"\{\{SECTION:(.+?)\}\}")


def markdown_to_hwpx_elements(markdown_text: str) -> list[str]:
    """Convert markdown text to list of HWPX XML paragraph strings.

    Uses mistune 3.x AST to parse markdown, then generates
    hp:p elements with appropriate formatting.

    Returns:
        List of XML strings, each representing one hp:p element.
    """
    try:
        import mistune
    except ImportError:
        logger.error("mistune not installed")
        return [_make_paragraph(markdown_text)]

    md = mistune.create_markdown(renderer="ast")
    tokens = md(markdown_text)
    elements: list[str] = []

    for token in tokens:
        ttype = token.get("type", "")
        if ttype == "heading":
            level = token.get("attrs", {}).get("level", 1)
            text = _extract_text_from_children(token.get("children", []))
            elements.append(_make_heading(text, level))
        elif ttype == "paragraph":
            runs = _children_to_runs(token.get("children", []))
            elements.append(_make_paragraph_with_runs(runs))
        elif ttype == "list":
            items = token.get("children", [])
            for item in items:
                text = _extract_text_from_children(
                    item.get("children", [{}])[0].get("children", [])
                    if item.get("children") else []
                )
                elements.append(_make_bullet(text))
        elif ttype == "table":
            elements.extend(_table_to_hwpx(token))
        elif ttype == "blank_line":
            continue
        else:
            # Fallback: extract text
            text = _extract_text_from_children(token.get("children", []))
            if text.strip():
                elements.append(_make_paragraph(text))

    return elements


def inject_content(
    template_path: str,
    sections: dict[str, str],
    output_path: str,
) -> str:
    """Inject markdown content into HWPX template.

    Finds {{SECTION:name}} placeholders in section*.xml files
    and replaces them with converted XML content.

    Args:
        template_path: Path to HWPX template file.
        sections: Dict of section_name → markdown content.
        output_path: Path for output HWPX file.

    Returns:
        Path to generated HWPX file.
    """
    try:
        from lxml import etree
    except ImportError as exc:
        raise ImportError("lxml required: pip install lxml") from exc

    # Copy template to output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    shutil.copy2(template_path, output_path)

    # Process each section*.xml
    with zipfile.ZipFile(output_path, "r") as zf_in:
        all_files = zf_in.namelist()
        section_files = [
            n for n in all_files
            if n.startswith("Contents/section") and n.endswith(".xml")
        ]
        file_contents = {}
        for name in all_files:
            file_contents[name] = zf_in.read(name)

    # Process section XMLs
    for section_file in section_files:
        xml_bytes = file_contents[section_file]
        root = etree.fromstring(xml_bytes)

        # Find paragraphs with placeholders
        ns = {"hp": _HP, "hs": _HS}
        paragraphs_to_replace: list[tuple] = []

        for p_elem in root.iter("{%s}p" % _HP):
            full_text = "".join(
                t.text or "" for t in p_elem.iter("{%s}t" % _HP)
            )
            match = _PLACEHOLDER_RE.search(full_text)
            if match:
                section_name = match.group(1)
                if section_name in sections:
                    paragraphs_to_replace.append((p_elem, section_name))

        # Replace placeholders with content (reverse order to preserve indices)
        for p_elem, section_name in reversed(paragraphs_to_replace):
            parent = p_elem.getparent()
            if parent is None:
                continue
            idx = list(parent).index(p_elem)
            parent.remove(p_elem)

            # Convert markdown to HWPX XML elements
            md_content = sections[section_name]
            xml_elements = markdown_to_hwpx_elements(md_content)

            for i, xml_str in enumerate(xml_elements):
                try:
                    new_elem = etree.fromstring(xml_str)
                    parent.insert(idx + i, new_elem)
                except etree.XMLSyntaxError:
                    # Fallback: plain text paragraph
                    fallback = etree.fromstring(_make_paragraph(md_content[:200]))
                    parent.insert(idx + i, fallback)
                    break

        # Serialize back
        file_contents[section_file] = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        )

    # Write output HWPX
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for name, data in file_contents.items():
            zf_out.writestr(name, data)

    return output_path


# ---------------------------------------------------------------------------
# Internal XML generators
# ---------------------------------------------------------------------------

def _make_paragraph(text: str) -> str:
    """Plain text paragraph."""
    escaped = _xml_escape(text)
    return (
        f'<hp:p xmlns:hp="{_HP}">'
        f"<hp:run><hp:t>{escaped}</hp:t></hp:run>"
        f"</hp:p>"
    )


def _make_paragraph_with_runs(runs: list[str]) -> str:
    """Paragraph with multiple formatted runs."""
    inner = "".join(runs)
    return f'<hp:p xmlns:hp="{_HP}">{inner}</hp:p>'


def _make_heading(text: str, level: int = 1) -> str:
    """Heading paragraph with style reference."""
    escaped = _xml_escape(text)
    bold = ' bold="true"' if level <= 2 else ""
    # Map heading level to approximate HWPX font size (1/100 pt)
    sizes = {1: "2400", 2: "2000", 3: "1600"}
    sz = sizes.get(level, "1600")
    return (
        f'<hp:p xmlns:hp="{_HP}">'
        f"<hp:run>"
        f'<hp:rPr{bold}><hp:sz val="{sz}"/></hp:rPr>'
        f"<hp:t>{escaped}</hp:t>"
        f"</hp:run>"
        f"</hp:p>"
    )


def _make_bullet(text: str) -> str:
    """Bullet list item paragraph."""
    escaped = _xml_escape(text)
    return (
        f'<hp:p xmlns:hp="{_HP}">'
        f"<hp:run><hp:t>  \u2022 {escaped}</hp:t></hp:run>"
        f"</hp:p>"
    )


def _table_to_hwpx(token: dict) -> list[str]:
    """Convert mistune table token to HWPX table XML."""
    # Simplified: render as formatted text paragraphs
    # Full hp:tbl support is Phase B+ enhancement
    elements: list[str] = []
    headers = token.get("children", [{}])[0].get("children", []) if token.get("children") else []
    if headers:
        header_text = " | ".join(
            _extract_text_from_children(h.get("children", [])) for h in headers
        )
        elements.append(_make_paragraph(f"[표] {header_text}"))

    rows = token.get("children", [{}])[1].get("children", []) if len(token.get("children", [])) > 1 else []
    for row in rows:
        cells = row.get("children", [])
        row_text = " | ".join(
            _extract_text_from_children(c.get("children", [])) for c in cells
        )
        elements.append(_make_paragraph(f"      {row_text}"))

    return elements


def _children_to_runs(children: list[dict]) -> list[str]:
    """Convert mistune AST children to HWPX run XML strings."""
    runs: list[str] = []
    for child in children:
        ctype = child.get("type", "")
        if ctype == "text":
            text = child.get("raw", child.get("children", ""))
            if isinstance(text, str) and text:
                runs.append(f"<hp:run><hp:t>{_xml_escape(text)}</hp:t></hp:run>")
        elif ctype == "strong":
            text = _extract_text_from_children(child.get("children", []))
            runs.append(
                f'<hp:run><hp:rPr bold="true"/><hp:t>{_xml_escape(text)}</hp:t></hp:run>'
            )
        elif ctype == "emphasis":
            text = _extract_text_from_children(child.get("children", []))
            runs.append(
                f'<hp:run><hp:rPr italic="true"/><hp:t>{_xml_escape(text)}</hp:t></hp:run>'
            )
        elif ctype == "codespan":
            text = child.get("raw", child.get("children", ""))
            if isinstance(text, str):
                runs.append(f"<hp:run><hp:t>[{_xml_escape(text)}]</hp:t></hp:run>")
        else:
            text = _extract_text_from_children(child.get("children", []))
            if text:
                runs.append(f"<hp:run><hp:t>{_xml_escape(text)}</hp:t></hp:run>")
    return runs


def _extract_text_from_children(children) -> str:
    """Recursively extract plain text from AST children."""
    if isinstance(children, str):
        return children
    if not isinstance(children, list):
        return ""
    parts = []
    for child in children:
        if isinstance(child, str):
            parts.append(child)
        elif isinstance(child, dict):
            raw = child.get("raw", "")
            if raw and isinstance(raw, str):
                parts.append(raw)
            else:
                parts.append(_extract_text_from_children(child.get("children", [])))
    return "".join(parts)


def _xml_escape(text: str) -> str:
    """Escape XML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
```

**Step 4: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_hwpx_injector.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add rag_engine/hwpx_injector.py rag_engine/tests/test_hwpx_injector.py
git commit -m "feat: add hwpx_injector for markdown-to-HWPX content injection"
```

---

### Task B-3: HWPX 템플릿 자동 분석 → profile.md 보강

**Files:**
- Modify: `rag_engine/company_profile_builder.py` (build_profile_md에 hwpx_styles 연동)
- Modify: `rag_engine/main.py` (HWPX 템플릿 업로드 엔드포인트)
- Test: `rag_engine/tests/test_company_profile_builder.py`

**Step 1: 테스트 추가**

```python
# test_company_profile_builder.py에 추가
def test_build_profile_md_with_hwpx_styles():
    """HWPX 스타일 정보가 profile.md에 반영."""
    from company_analyzer import StyleProfile
    hwpx_styles = {
        "body_font": "함초롬바탕",
        "heading_font": "함초롬돋움",
        "body_font_size": 11.0,
        "line_spacing": "160%",
        "margins": "상3.0/하2.5/좌3.0/우2.5cm",
    }
    md = build_profile_md(
        company_name="테스트기업",
        style=StyleProfile(tone="경어체"),
        hwpx_styles=hwpx_styles,
    )
    assert "함초롬바탕" in md
    assert "함초롬돋움" in md
    assert "160%" in md
```

**Step 2: 테스트 실패 확인 (이미 hwpx_styles 파라미터 있으므로 통과할 수 있음)**

Run: `cd rag_engine && pytest tests/test_company_profile_builder.py -v`

**Step 3: main.py에 HWPX 템플릿 업로드 엔드포인트 추가**

```python
# main.py에 추가
@app.post("/api/company-profile/upload-template")
async def upload_hwpx_template(file: UploadFile = File(...)):
    """Upload HWPX template and auto-enrich profile.md with extracted styles."""
    from hwpx_parser import is_hwpx_file, extract_hwpx_styles
    from company_profile_builder import load_profile_md, save_profile_md, build_profile_md

    if not file.filename or not file.filename.endswith(".hwpx"):
        raise HTTPException(400, "HWPX 파일만 업로드 가능합니다.")

    skills_dir = _get_company_skills_dir()
    templates_dir = os.path.join(skills_dir, "templates")
    os.makedirs(templates_dir, exist_ok=True)

    # Save template
    safe_name = _re.sub(r"[^a-zA-Z0-9가-힣._\-]", "_", file.filename)[:100]
    template_path = os.path.join(templates_dir, safe_name)
    content = await file.read()
    with open(template_path, "wb") as f:
        f.write(content)

    # Extract styles
    hwpx_styles = await asyncio.to_thread(extract_hwpx_styles, template_path)

    # Enrich profile.md if exists, or create minimal one
    existing_md = load_profile_md(skills_dir)
    if not existing_md:
        from company_analyzer import StyleProfile
        profile_md = build_profile_md("미설정", StyleProfile(), hwpx_styles=hwpx_styles)
        save_profile_md(skills_dir, profile_md)
    # TODO: merge hwpx_styles into existing profile (Phase B enhancement)

    return {
        "ok": True,
        "template_path": safe_name,
        "extracted_styles": hwpx_styles,
    }
```

**Step 4: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_company_profile_builder.py -v`
Expected: ALL passed

**Step 5: Commit**

```bash
git add rag_engine/company_profile_builder.py rag_engine/main.py rag_engine/tests/test_company_profile_builder.py
git commit -m "feat: auto-enrich profile.md from HWPX template styles"
```

---

### Task B-4: proposal_orchestrator — HWPX 출력 경로 추가

**Files:**
- Modify: `rag_engine/proposal_orchestrator.py`
- Test: `rag_engine/tests/test_proposal_orchestrator.py`

**Context:**
- `output_format: str = "docx"` 파라미터 추가
- `"hwpx"` 선택 시: company_skills_dir에서 템플릿 검색 → hwpx_injector로 주입
- 템플릿 없으면 `_default/` 폴백 → 그것도 없으면 DOCX 폴백
- `ProposalResult`에 `hwpx_path` 필드 추가

**Step 1: 테스트 추가**

```python
# test_proposal_orchestrator.py에 추가
def test_generate_proposal_hwpx_output(tmp_path):
    """output_format='hwpx' 시 HWPX 파일 생성."""
    from unittest.mock import patch, MagicMock
    import zipfile

    # 템플릿 HWPX 생성
    skills_dir = str(tmp_path / "skills")
    templates_dir = os.path.join(skills_dir, "templates")
    os.makedirs(templates_dir, exist_ok=True)
    template_path = os.path.join(templates_dir, "proposal_template.hwpx")
    section_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
         xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>{{SECTION:개요}}</hp:t></hp:run></hp:p>
</hs:sec>"""
    with zipfile.ZipFile(template_path, "w") as zf:
        zf.writestr("Contents/section0.xml", section_xml)
        zf.writestr("Contents/content.hpf", "<hpf/>")

    rfx = {"title": "테스트", "issuing_org": "기관"}
    mock_kb = MagicMock()
    mock_kb.search.return_value = []

    with patch("proposal_orchestrator.KnowledgeDB", return_value=mock_kb), \
         patch("proposal_orchestrator.write_section", return_value="## 개요\n\n내용"), \
         patch("proposal_orchestrator.build_proposal_outline") as mock_outline:
        from knowledge_models import ProposalSection, ProposalOutline
        mock_outline.return_value = ProposalOutline(
            title="테스트",
            issuing_org="기관",
            sections=[ProposalSection(name="개요", evaluation_item="이해도", max_score=10, weight=0.1)],
        )

        from proposal_orchestrator import generate_proposal
        result = generate_proposal(
            rfx_result=rfx,
            output_dir=str(tmp_path / "out"),
            knowledge_db_path=str(tmp_path / "kb"),
            company_skills_dir=skills_dir,
            output_format="hwpx",
        )

    assert result.hwpx_path
    assert result.hwpx_path.endswith(".hwpx")
    assert os.path.exists(result.hwpx_path)


def test_generate_proposal_hwpx_fallback_to_docx(tmp_path):
    """HWPX 템플릿 없으면 DOCX 폴백."""
    from unittest.mock import patch, MagicMock

    rfx = {"title": "테스트", "issuing_org": "기관"}
    mock_kb = MagicMock()
    mock_kb.search.return_value = []

    with patch("proposal_orchestrator.KnowledgeDB", return_value=mock_kb), \
         patch("proposal_orchestrator.write_section", return_value="내용"), \
         patch("proposal_orchestrator.build_proposal_outline") as mock_outline, \
         patch("proposal_orchestrator.assemble_docx", return_value=str(tmp_path / "out.docx")):
        from knowledge_models import ProposalSection, ProposalOutline
        mock_outline.return_value = ProposalOutline(
            title="테스트",
            issuing_org="기관",
            sections=[ProposalSection(name="개요", evaluation_item="이해도", max_score=10, weight=0.1)],
        )

        from proposal_orchestrator import generate_proposal
        result = generate_proposal(
            rfx_result=rfx,
            output_dir=str(tmp_path / "out"),
            knowledge_db_path=str(tmp_path / "kb"),
            company_skills_dir=str(tmp_path / "no_skills"),
            output_format="hwpx",
        )

    # 템플릿 없으므로 DOCX 폴백
    assert result.docx_path.endswith(".docx")
```

**Step 2: proposal_orchestrator.py 수정**

```python
# ProposalResult에 hwpx_path 추가
@dataclass
class ProposalResult:
    docx_path: str = ""             # ← 기본값 "" 으로 변경
    hwpx_path: str = ""             # ← 추가
    sections: list[tuple[str, str]] = field(default_factory=list)
    outline: ProposalOutline = None
    quality_issues: list[QualityIssue] = field(default_factory=list)
    generation_time_sec: float = 0.0

# generate_proposal 시그니처에 output_format 추가
def generate_proposal(
    ...
    output_format: str = "docx",    # "docx" | "hwpx"
    ...
) -> ProposalResult:

# 6. Assemble output — output_format 분기
    hwpx_path = ""
    docx_path = ""

    if output_format == "hwpx":
        hwpx_path = _try_hwpx_output(
            sections, rfx_result, output_dir, company_skills_dir, ts, safe_title
        )

    if not hwpx_path:
        # DOCX 폴백
        docx_path = _assemble_docx_output(...)
```

**Step 3: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_proposal_orchestrator.py -v`
Expected: ALL passed

**Step 4: Commit**

```bash
git add rag_engine/proposal_orchestrator.py rag_engine/tests/test_proposal_orchestrator.py
git commit -m "feat: add HWPX output path in proposal_orchestrator"
```

---

## Phase C: 학습 루프 + 버전 관리

### Task C-1: company_profile_updater.py — diff → profile.md 업데이트

**Files:**
- Create: `rag_engine/company_profile_updater.py`
- Test: `rag_engine/tests/test_company_profile_updater.py`

**Context:**
- auto_learner가 3회 이상 반복 패턴을 감지하면 profile.md 업데이트 트리거
- profile.md의 해당 섹션만 업데이트 (전체 재생성 아님)
- 업데이트 전 이전 버전을 profile_history/에 보관

**Step 1: 테스트 작성**

```python
# rag_engine/tests/test_company_profile_updater.py
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from company_profile_updater import (
    update_profile_section,
    backup_profile_version,
    load_changelog,
)


def test_update_profile_section(tmp_path):
    """profile.md의 특정 섹션만 업데이트."""
    company_dir = str(tmp_path / "comp")
    os.makedirs(company_dir)
    # 초기 profile.md
    profile_md = (
        "# 테스트 프로필\n\n"
        "## 문체\n- 어미: ~이다 (격식체)\n\n"
        "## 강점 표현 패턴\n- (미설정)\n"
    )
    with open(os.path.join(company_dir, "profile.md"), "w") as f:
        f.write(profile_md)

    update_profile_section(
        company_dir=company_dir,
        section_name="문체",
        new_content="- 어미: ~합니다 (경어체)\n- 평균 문장 길이: 30자",
    )

    with open(os.path.join(company_dir, "profile.md")) as f:
        updated = f.read()

    assert "경어체" in updated
    assert "30자" in updated
    # 다른 섹션은 유지
    assert "## 강점 표현 패턴" in updated


def test_backup_profile_version(tmp_path):
    """버전 백업 생성."""
    company_dir = str(tmp_path / "comp")
    os.makedirs(company_dir)
    with open(os.path.join(company_dir, "profile.md"), "w") as f:
        f.write("original content")

    version = backup_profile_version(company_dir, reason="톤 수정 반영")
    assert version >= 1

    history_dir = os.path.join(company_dir, "profile_history")
    assert os.path.isdir(history_dir)
    files = os.listdir(history_dir)
    assert any(f.startswith("profile_v") and f.endswith(".md") for f in files)
    assert "changelog.json" in files


def test_changelog_records(tmp_path):
    """changelog.json에 변경 기록 추가."""
    company_dir = str(tmp_path / "comp")
    os.makedirs(company_dir)
    with open(os.path.join(company_dir, "profile.md"), "w") as f:
        f.write("content")

    backup_profile_version(company_dir, reason="첫 번째 수정")
    backup_profile_version(company_dir, reason="두 번째 수정")

    changelog = load_changelog(company_dir)
    assert len(changelog["versions"]) == 2
    assert changelog["versions"][0]["reason"] == "첫 번째 수정"
    assert changelog["versions"][1]["reason"] == "두 번째 수정"
```

**Step 2: 구현**

```python
# rag_engine/company_profile_updater.py
"""Company Profile Updater — update profile.md sections from learned patterns.

Triggered by auto_learner when patterns reach 3+ occurrences.
Maintains version history for rollback capability.
"""
from __future__ import annotations

import json
import os
import logging
import re
import shutil
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


def update_profile_section(
    company_dir: str,
    section_name: str,
    new_content: str,
    backup: bool = True,
) -> bool:
    """Update a specific section in profile.md.

    Args:
        company_dir: Path to company_skills/{company_id}/.
        section_name: Section heading (without ##) to replace.
        new_content: New content for the section body.
        backup: Whether to create a version backup first.

    Returns:
        True if update succeeded, False otherwise.
    """
    profile_path = os.path.join(company_dir, "profile.md")
    if not os.path.isfile(profile_path):
        return False

    with open(profile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find section boundaries
    pattern = re.compile(
        rf"(## {re.escape(section_name)}\n)(.*?)(?=\n## |\Z)",
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        logger.warning("Section '%s' not found in profile.md", section_name)
        return False

    if backup:
        backup_profile_version(company_dir, reason=f"{section_name} 섹션 업데이트")

    # Replace section content
    new_section = f"## {section_name}\n{new_content}\n"
    updated = content[:match.start()] + new_section + content[match.end():]

    # Update learning history
    today = date.today().isoformat()
    history_line = f"- {today}: {section_name} 섹션 업데이트 (auto_learner)"
    if "## 학습 이력" in updated:
        updated = updated.rstrip() + f"\n{history_line}\n"
    else:
        updated += f"\n## 학습 이력\n{history_line}\n"

    # Atomic write
    tmp_path = profile_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(updated)
    os.replace(tmp_path, profile_path)

    return True


def backup_profile_version(company_dir: str, reason: str = "") -> int:
    """Backup current profile.md to profile_history/.

    Returns:
        Version number of the backup.
    """
    profile_path = os.path.join(company_dir, "profile.md")
    history_dir = os.path.join(company_dir, "profile_history")
    os.makedirs(history_dir, exist_ok=True)

    # Determine version number
    changelog = load_changelog(company_dir)
    version = len(changelog.get("versions", [])) + 1

    # Copy profile
    backup_name = f"profile_v{version:03d}.md"
    shutil.copy2(profile_path, os.path.join(history_dir, backup_name))

    # Update changelog
    changelog.setdefault("versions", []).append({
        "version": version,
        "date": date.today().isoformat(),
        "reason": reason,
        "proposals_after": 0,
        "edit_rate_after": None,
    })
    _save_changelog(company_dir, changelog)

    return version


def load_changelog(company_dir: str) -> dict:
    """Load changelog.json from profile_history/."""
    path = os.path.join(company_dir, "profile_history", "changelog.json")
    if not os.path.isfile(path):
        return {"versions": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_changelog(company_dir: str, changelog: dict) -> None:
    """Save changelog.json atomically."""
    history_dir = os.path.join(company_dir, "profile_history")
    os.makedirs(history_dir, exist_ok=True)
    path = os.path.join(history_dir, "changelog.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(changelog, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
```

**Step 3: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_company_profile_updater.py -v`
Expected: 3 passed

**Step 4: Commit**

```bash
git add rag_engine/company_profile_updater.py rag_engine/tests/test_company_profile_updater.py
git commit -m "feat: add company_profile_updater with version history"
```

---

### Task C-2: auto_learner → profile.md 업데이트 트리거 연결

**Files:**
- Modify: `rag_engine/auto_learner.py` (패턴 승격 시 profile 업데이트 콜백)
- Modify: `rag_engine/main.py` (edit-feedback 엔드포인트에서 profile 업데이트 연동)
- Test: `rag_engine/tests/test_auto_learner.py`

**Step 1: 테스트 추가**

```python
# test_auto_learner.py에 추가
def test_promoted_pattern_triggers_profile_callback():
    """3회 반복 패턴 승격 시 콜백 호출."""
    from unittest.mock import MagicMock
    callback = MagicMock()

    for i in range(3):
        result = process_edit_feedback(
            company_id="cb_test",
            section_name="문체",
            original_text="이것은 테스트이다.",
            edited_text="이것은 테스트입니다.",
            doc_type="proposal",
            on_pattern_promoted=callback if i == 2 else None,
        )

    # 3회차에서 콜백 호출
    assert callback.called
    args = callback.call_args[0]
    assert args[0] == "cb_test"  # company_id
    assert len(args[1]) >= 1     # promoted patterns
```

**Step 2: auto_learner.py에 on_pattern_promoted 콜백 추가**

`process_edit_feedback()` 시그니처에 `on_pattern_promoted` 파라미터 추가:

```python
def process_edit_feedback(
    company_id: str,
    section_name: str,
    original_text: str,
    edited_text: str,
    doc_type: str = "proposal",
    on_pattern_promoted: Optional[callable] = None,  # ← 추가
) -> LearningResult:
```

패턴 승격 시 콜백 호출:

```python
    # 기존 승격 로직 뒤에 추가
    if promoted and on_pattern_promoted:
        try:
            on_pattern_promoted(company_id, promoted)
        except Exception as exc:
            logger.warning("Profile update callback failed: %s", exc)
```

**Step 3: main.py의 edit-feedback에서 profile 업데이트 연동**

```python
# /api/edit-feedback 핸들러 내부
def _on_pattern_promoted(company_id, patterns):
    """Auto-learner 패턴 승격 시 profile.md 업데이트."""
    try:
        from company_profile_updater import update_profile_section
        skills_dir = _get_company_skills_dir()
        for pattern in patterns:
            update_profile_section(
                company_dir=skills_dir,
                section_name="문체",  # 패턴 유형에 따라 분기
                new_content=f"- 학습된 패턴: {pattern.description}",
            )
    except Exception as exc:
        logger.debug("Profile update skipped: %s", exc)
```

**Step 4: 테스트 통과 확인**

Run: `cd rag_engine && pytest tests/test_auto_learner.py -v`
Expected: ALL passed

**Step 5: 전체 회귀 테스트**

Run: `cd rag_engine && pytest -q`
Expected: 기존 160+ 테스트 + 신규 ~20개 모두 통과

**Step 6: Commit**

```bash
git add rag_engine/auto_learner.py rag_engine/main.py rag_engine/tests/test_auto_learner.py
git commit -m "feat: connect auto_learner pattern promotion to profile.md updates"
```

---

## 전체 검증

### Final Verification

```bash
# 1. 전체 테스트
cd rag_engine && pytest -q
# 기대: 160 기존 + ~20 신규 = ~180 통과

# 2. 신규 모듈 개별 검증
cd rag_engine && pytest tests/test_company_profile_builder.py tests/test_hwpx_parser.py tests/test_hwpx_injector.py tests/test_company_profile_updater.py tests/test_profile_api.py -v

# 3. 기존 기능 회귀 확인
cd rag_engine && pytest tests/test_proposal_orchestrator.py tests/test_proposal_api.py tests/test_section_writer.py tests/test_auto_learner.py -v
```

---

## 신규 파일 요약

| 파일 | Task | 역할 |
|---|---|---|
| `company_profile_builder.py` | A-1 | StyleProfile → profile.md 마크다운 변환 + save/load |
| `hwpx_parser.py` | B-1 | HWPX 텍스트 추출 + 스타일 분석 (zipfile + lxml) |
| `hwpx_injector.py` | B-2 | 마크다운 → HWPX XML 변환 + 템플릿 주입 (mistune + lxml) |
| `company_profile_updater.py` | C-1 | profile.md 섹션 업데이트 + 버전 관리 |
| `tests/test_company_profile_builder.py` | A-1 | profile builder 테스트 |
| `tests/test_profile_api.py` | A-4 | profile CRUD API 테스트 |
| `tests/test_hwpx_parser.py` | B-1 | HWPX 파서 테스트 |
| `tests/test_hwpx_injector.py` | B-2 | HWPX 인젝터 테스트 |
| `tests/test_company_profile_updater.py` | C-1 | profile updater 테스트 |

## 수정 파일 요약

| 파일 | Task | 변경 |
|---|---|---|
| `requirements.txt` | A-0 | lxml + python-hwpx 추가 |
| `section_writer.py` | A-2 | profile_md 파라미터 + 5계층 프롬프트 |
| `proposal_orchestrator.py` | A-3, B-4 | company_skills_dir + output_format 분기 |
| `main.py` | A-4, A-5, B-3 | profile CRUD + 템플릿 업로드 + v2 연동 |
| `auto_learner.py` | C-2 | on_pattern_promoted 콜백 |
