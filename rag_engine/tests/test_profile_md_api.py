"""Tests for profile.md CRUD API endpoints.

Covers:
- GET  /api/company-profile/md          — parse profile into sections
- PUT  /api/company-profile/md/section  — update a single section
- GET  /api/company-profile/md/history  — version history
- POST /api/company-profile/md/rollback — rollback to a past version
"""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Seed data — a realistic profile.md with all 6 sections
# ---------------------------------------------------------------------------

SEED_PROFILE_MD = """\
# 테스트기업 회사 프로필

> 생성일: 2026-02-28 12:00 UTC

## 문서 스타일

**구조 패턴**: 서론-본론-결론 3단 구성

**용어 매핑**:
- 클라우드 → 클라우드 컴퓨팅
- AI → 인공지능

## 문체

- **문체 유형**: 공식적-간결
- **평균 문장 길이**: 42자

**빈출 표현**:
- "당사는"
- "본 사업"

## 강점 표현 패턴

**강점 키워드**:
- 10년 이상 경력
- ISO 27001 인증

## 평가항목별 전략

| 평가항목 | 비중 |
|---------|------|
| 기술 | 40.0% |
| 가격 | 30.0% |

## HWPX 생성 규칙

- **본문 글꼴**: 함초롬바탕
- **줄 간격**: 160%

## 학습 이력

(아직 학습된 패턴이 없습니다. 제안서 수정 시 자동으로 기록됩니다.)
"""


@pytest.fixture()
def seeded_dir(tmp_path):
    """Create a company_skills directory with a seeded profile.md."""
    company_dir = tmp_path / "default"
    company_dir.mkdir(parents=True)
    (company_dir / "profile.md").write_text(SEED_PROFILE_MD, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def client(seeded_dir, monkeypatch):
    """TestClient whose _get_company_skills_dir points at seeded_dir."""
    monkeypatch.setattr(
        "main._get_company_skills_dir",
        lambda company_id="default": str(seeded_dir / company_id),
    )
    from main import app

    return TestClient(app)


@pytest.fixture()
def empty_client(tmp_path, monkeypatch):
    """TestClient whose company dir has no profile.md."""
    monkeypatch.setattr(
        "main._get_company_skills_dir",
        lambda company_id="default": str(tmp_path / company_id),
    )
    from main import app

    return TestClient(app)


# ===================================================================
# GET /api/company-profile/md
# ===================================================================


class TestGetProfileMd:
    """GET /api/company-profile/md — parse profile into sections."""

    def test_returns_sections_when_profile_exists(self, client):
        resp = client.get("/api/company-profile/md", params={"company_id": "default"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        sections = data["sections"]
        assert isinstance(sections, list)
        assert len(sections) == 6

        # Verify section names
        names = [s["name"] for s in sections]
        assert names == [
            "문서 스타일",
            "문체",
            "강점 표현 패턴",
            "평가항목별 전략",
            "HWPX 생성 규칙",
            "학습 이력",
        ]

        # 학습 이력 is not editable
        history_section = next(s for s in sections if s["name"] == "학습 이력")
        assert history_section["editable"] is False

        # All other sections are editable
        for s in sections:
            if s["name"] != "학습 이력":
                assert s["editable"] is True

    def test_section_content_is_populated(self, client):
        resp = client.get("/api/company-profile/md", params={"company_id": "default"})
        data = resp.json()
        doc_style = next(s for s in data["sections"] if s["name"] == "문서 스타일")
        assert "구조 패턴" in doc_style["content"]
        assert "서론-본론-결론" in doc_style["content"]

    def test_returns_empty_sections_when_no_profile(self, empty_client):
        resp = empty_client.get(
            "/api/company-profile/md", params={"company_id": "default"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["sections"] == []

    def test_uses_default_company_id(self, client):
        """company_id parameter defaults to 'default'."""
        resp = client.get("/api/company-profile/md")
        assert resp.status_code == 200
        assert len(resp.json()["sections"]) == 6


# ===================================================================
# PUT /api/company-profile/md/section
# ===================================================================


class TestUpdateProfileSection:
    """PUT /api/company-profile/md/section — update a single section."""

    def test_update_section_successfully(self, client, seeded_dir):
        new_content = "**구조 패턴**: 4단 구성 (현황-분석-제안-기대효과)\n"
        resp = client.put(
            "/api/company-profile/md/section",
            json={
                "company_id": "default",
                "section_name": "문서 스타일",
                "content": new_content,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["section_name"] == "문서 스타일"

        # Verify the file was actually updated
        profile_path = seeded_dir / "default" / "profile.md"
        content = profile_path.read_text(encoding="utf-8")
        assert "4단 구성" in content
        # Old content should be gone
        assert "서론-본론-결론 3단 구성" not in content

    def test_update_creates_backup(self, client, seeded_dir):
        """Update should automatically create a version backup."""
        resp = client.put(
            "/api/company-profile/md/section",
            json={
                "section_name": "문체",
                "content": "- **문체 유형**: 비공식-상세\n",
            },
        )
        assert resp.status_code == 200

        # Check that backup was created
        history_dir = seeded_dir / "default" / "profile_history"
        assert history_dir.exists()
        backup_files = list(history_dir.glob("profile_v*.md"))
        assert len(backup_files) >= 1

        # Check changelog
        changelog_path = history_dir / "changelog.json"
        assert changelog_path.exists()
        changelog = json.loads(changelog_path.read_text(encoding="utf-8"))
        assert len(changelog["versions"]) >= 1

    def test_update_nonexistent_section_fails(self, client):
        resp = client.put(
            "/api/company-profile/md/section",
            json={
                "section_name": "존재하지 않는 섹션",
                "content": "내용",
            },
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower() or "없" in resp.json()["detail"]

    def test_update_when_no_profile_fails(self, empty_client):
        resp = empty_client.put(
            "/api/company-profile/md/section",
            json={
                "section_name": "문서 스타일",
                "content": "새 내용",
            },
        )
        assert resp.status_code == 404

    def test_update_validates_empty_section_name(self, client):
        resp = client.put(
            "/api/company-profile/md/section",
            json={
                "section_name": "",
                "content": "내용",
            },
        )
        assert resp.status_code == 422

    def test_update_validates_content_max_length(self, client):
        resp = client.put(
            "/api/company-profile/md/section",
            json={
                "section_name": "문체",
                "content": "x" * 50_001,
            },
        )
        assert resp.status_code == 422


# ===================================================================
# GET /api/company-profile/md/history
# ===================================================================


class TestProfileHistory:
    """GET /api/company-profile/md/history — version history."""

    def test_empty_history_initially(self, client):
        resp = client.get(
            "/api/company-profile/md/history",
            params={"company_id": "default"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["versions"] == []

    def test_history_after_update(self, client):
        """After updating a section, history should contain one entry."""
        # Perform an update to create a backup
        client.put(
            "/api/company-profile/md/section",
            json={
                "section_name": "문체",
                "content": "- **문체 유형**: 비공식\n",
            },
        )

        resp = client.get(
            "/api/company-profile/md/history",
            params={"company_id": "default"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["versions"]) == 1
        entry = data["versions"][0]
        assert entry["version"] == 1
        assert "date" in entry
        assert "reason" in entry

    def test_history_accumulates(self, client):
        """Multiple updates create multiple history entries."""
        client.put(
            "/api/company-profile/md/section",
            json={"section_name": "문체", "content": "v1\n"},
        )
        client.put(
            "/api/company-profile/md/section",
            json={"section_name": "강점 표현 패턴", "content": "v2\n"},
        )

        resp = client.get("/api/company-profile/md/history")
        data = resp.json()
        assert len(data["versions"]) == 2
        assert data["versions"][0]["version"] == 1
        assert data["versions"][1]["version"] == 2

    def test_uses_default_company_id(self, client):
        resp = client.get("/api/company-profile/md/history")
        assert resp.status_code == 200


# ===================================================================
# POST /api/company-profile/md/rollback
# ===================================================================


class TestRollbackProfile:
    """POST /api/company-profile/md/rollback — restore a past version."""

    def test_rollback_restores_old_version(self, client, seeded_dir):
        # Step 1: Update to create version 1 backup (original content)
        client.put(
            "/api/company-profile/md/section",
            json={
                "section_name": "문서 스타일",
                "content": "**구조 패턴**: 변경된 내용\n",
            },
        )

        # Verify the update took effect
        profile_path = seeded_dir / "default" / "profile.md"
        assert "변경된 내용" in profile_path.read_text(encoding="utf-8")

        # Step 2: Rollback to version 1 (the backup of the original)
        resp = client.post(
            "/api/company-profile/md/rollback",
            json={"target_version": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["restored_version"] == 1

        # Verify the content is restored to the original
        restored = profile_path.read_text(encoding="utf-8")
        assert "서론-본론-결론 3단 구성" in restored
        assert "변경된 내용" not in restored

    def test_rollback_nonexistent_version_fails(self, client):
        resp = client.post(
            "/api/company-profile/md/rollback",
            json={"target_version": 999},
        )
        assert resp.status_code == 404

    def test_rollback_validates_version_ge_1(self, client):
        resp = client.post(
            "/api/company-profile/md/rollback",
            json={"target_version": 0},
        )
        assert resp.status_code == 422

    def test_rollback_when_no_profile_dir_fails(self, empty_client):
        resp = empty_client.post(
            "/api/company-profile/md/rollback",
            json={"target_version": 1},
        )
        assert resp.status_code == 404

    def test_rollback_creates_new_changelog_entry(self, client, seeded_dir):
        """Rollback should add an entry to the changelog."""
        # Create a backup first
        client.put(
            "/api/company-profile/md/section",
            json={"section_name": "문체", "content": "변경\n"},
        )

        # Rollback
        client.post(
            "/api/company-profile/md/rollback",
            json={"target_version": 1},
        )

        # Check changelog has both original backup + rollback backup entries
        changelog_path = seeded_dir / "default" / "profile_history" / "changelog.json"
        changelog = json.loads(changelog_path.read_text(encoding="utf-8"))
        # Version 1 from the update, version 2 from the rollback backup
        assert len(changelog["versions"]) >= 2
