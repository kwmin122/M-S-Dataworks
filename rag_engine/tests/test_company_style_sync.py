"""Tests for style analysis → profile.md section-level sync.

Verifies that:
1. analyze-company-style endpoint auto-syncs style sections to profile.md
2. Non-style sections (HWPX rules, learning history) are preserved
3. profile.md is created if it doesn't exist
4. Backup/history is created on update
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from company_analyzer import StyleProfile


@pytest.fixture
def style_sync_client(tmp_path):
    """TestClient with isolated company_skills + company_db dirs."""
    company_skills_base = str(tmp_path / "company_skills")
    company_db_base = str(tmp_path / "company_db")
    os.makedirs(company_skills_base, exist_ok=True)
    os.makedirs(company_db_base, exist_ok=True)

    import main as _main
    original_cache = _main._company_db_cache.copy()
    original_db_base = _main._COMPANY_DB_BASE
    original_embedding_fn = _main._company_db_embedding_fn

    _main._company_db_cache.clear()
    _main._COMPANY_DB_BASE = company_db_base
    _main.limiter.enabled = False

    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    _main._company_db_embedding_fn = DefaultEmbeddingFunction()

    # Patch _get_company_skills_dir to use tmp_path
    def _mock_skills_dir(company_id="default"):
        d = os.path.join(company_skills_base, company_id)
        os.makedirs(d, exist_ok=True)
        return d

    with patch("main._get_company_skills_dir", side_effect=_mock_skills_dir):
        from main import app
        client = TestClient(app)
        try:
            yield client, company_skills_base, company_db_base
        finally:
            _main._company_db_cache.clear()
            _main._company_db_cache.update(original_cache)
            _main._COMPANY_DB_BASE = original_db_base
            _main._company_db_embedding_fn = original_embedding_fn


def test_style_analysis_creates_profile_md_when_missing(style_sync_client):
    """profile.md가 없을 때 style 분석 후 자동 생성."""
    client, skills_base, _ = style_sync_client
    company_id = "test_co"

    # Mock LLM call in analyze_company_style
    mock_style = StyleProfile(
        tone="격식체",
        avg_sentence_length=28.5,
        structure_pattern="개요(20%) → 기술(40%) → 관리(20%) → 가격(20%)",
        strength_keywords=["클라우드", "AI", "보안"],
        terminology={},
        common_phrases=["최적의 솔루션을 제공합니다"],
        section_weight_pattern={"기술": 0.4, "관리": 0.2},
    )

    with patch("company_analyzer.analyze_company_style", return_value=mock_style):
        resp = client.post("/api/company-db/analyze-style", json={
            "company_id": company_id,
            "documents": ["테스트 제안서 내용입니다."],
        })

    assert resp.status_code == 200

    # profile.md should now exist
    from company_profile_builder import load_profile_md
    skills_dir = os.path.join(skills_base, company_id)
    content = load_profile_md(skills_dir)
    assert content != "", "profile.md should be created"
    assert "격식체" in content
    assert "28.5" in content
    assert "클라우드" in content


def test_style_analysis_updates_only_style_sections(style_sync_client):
    """profile.md가 있을 때 style 섹션만 갱신, 다른 섹션은 보존."""
    client, skills_base, _ = style_sync_client
    company_id = "test_co"

    # Pre-create profile.md with custom HWPX and learning history
    skills_dir = os.path.join(skills_base, company_id)
    os.makedirs(skills_dir, exist_ok=True)
    from company_profile_builder import save_profile_md
    original_content = """# test_co 회사 프로필

## 문서 스타일
**구조 패턴**: (분석 데이터 없음)
**용어 매핑**: (등록된 용어 없음)

## 문체
- **문체 유형**: 미분석
- **평균 문장 길이**: 0.0자

## 강점 표현 패턴
**강점 키워드**: (분석 데이터 없음)

## 평가항목별 전략
(평가항목 분석 데이터 없음)

## HWPX 생성 규칙
- **본문 글꼴**: 맑은 고딕
- **제목 글꼴**: 나눔고딕 Bold

## 학습 이력
- 2026-03-10: 문체 섹션 업데이트 (사용자 편집)
"""
    save_profile_md(skills_dir, original_content)

    # Run style analysis
    mock_style = StyleProfile(
        tone="경어체",
        avg_sentence_length=32.0,
        structure_pattern="요약(10%) → 본론(60%) → 결론(30%)",
        strength_keywords=["혁신", "디지털전환"],
        terminology={},
        common_phrases=["검증된 방법론"],
        section_weight_pattern={"기술": 0.6, "관리": 0.4},
    )

    with patch("company_analyzer.analyze_company_style", return_value=mock_style):
        resp = client.post("/api/company-db/analyze-style", json={
            "company_id": company_id,
            "documents": ["새로운 제안서 내용"],
        })

    assert resp.status_code == 200

    from company_profile_builder import load_profile_md
    updated = load_profile_md(skills_dir)

    # Style sections should be updated
    assert "경어체" in updated, "문체 should be updated"
    assert "32.0" in updated, "avg_sentence_length should be updated"
    assert "혁신" in updated, "strength_keywords should be updated"

    # Non-style sections should be preserved
    assert "맑은 고딕" in updated, "HWPX rules should be preserved"
    assert "나눔고딕 Bold" in updated, "HWPX rules should be preserved"
    assert "2026-03-10" in updated, "Learning history should be preserved"


def test_style_analysis_creates_backup(style_sync_client):
    """style 동기화 시 backup이 생성되는지 확인."""
    client, skills_base, _ = style_sync_client
    company_id = "test_co"

    # Pre-create profile.md
    skills_dir = os.path.join(skills_base, company_id)
    os.makedirs(skills_dir, exist_ok=True)
    from company_profile_builder import save_profile_md, build_profile_md
    save_profile_md(skills_dir, build_profile_md("test_co"))

    mock_style = StyleProfile(
        tone="격식체",
        avg_sentence_length=25.0,
    )

    with patch("company_analyzer.analyze_company_style", return_value=mock_style):
        resp = client.post("/api/company-db/analyze-style", json={
            "company_id": company_id,
            "documents": ["내용"],
        })

    assert resp.status_code == 200

    # Exactly 1 backup version (not 4)
    history_dir = os.path.join(skills_dir, "profile_history")
    assert os.path.isdir(history_dir), "profile_history dir should exist"
    backups = [f for f in os.listdir(history_dir) if f.endswith(".md")]
    assert len(backups) == 1, f"Expected exactly 1 backup, got {len(backups)}"

    # Exactly 1 changelog entry
    import json
    changelog_path = os.path.join(history_dir, "changelog.json")
    with open(changelog_path) as f:
        changelog = json.load(f)
    assert len(changelog["versions"]) == 1, f"Expected 1 changelog entry, got {len(changelog['versions'])}"
    assert "스타일 분석 동기화" in changelog["versions"][0]["reason"]

    # Exactly 1 history line for sync (not 4 auto_learner lines)
    from company_profile_builder import load_profile_md
    updated = load_profile_md(skills_dir)
    sync_lines = [l for l in updated.splitlines() if "스타일 분석 동기화" in l]
    assert len(sync_lines) == 1, f"Expected 1 sync history line, got {len(sync_lines)}"
    learner_lines = [l for l in updated.splitlines() if "auto_learner" in l]
    assert len(learner_lines) == 0, f"Expected 0 auto_learner lines, got {len(learner_lines)}"
