from __future__ import annotations
import sys
import os

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
    profile_md = (
        "# 테스트 프로필\n\n"
        "## 문체\n- 어미: ~이다 (격식체)\n\n"
        "## 강점 표현 패턴\n- (미설정)\n"
    )
    with open(os.path.join(company_dir, "profile.md"), "w") as f:
        f.write(profile_md)

    result = update_profile_section(
        company_dir=company_dir,
        section_name="문체",
        new_content="- 어미: ~합니다 (경어체)\n- 평균 문장 길이: 30자",
    )
    assert result is True

    with open(os.path.join(company_dir, "profile.md")) as f:
        updated = f.read()

    assert "경어체" in updated
    assert "30자" in updated
    # Other sections preserved
    assert "## 강점 표현 패턴" in updated


def test_update_profile_section_missing_file(tmp_path):
    """Missing profile.md returns False."""
    result = update_profile_section(
        company_dir=str(tmp_path / "nonexistent"),
        section_name="문체",
        new_content="new content",
    )
    assert result is False


def test_update_profile_section_missing_section(tmp_path):
    """Non-existent section returns False."""
    company_dir = str(tmp_path / "comp")
    os.makedirs(company_dir)
    with open(os.path.join(company_dir, "profile.md"), "w") as f:
        f.write("## 문체\n- test\n")

    result = update_profile_section(
        company_dir=company_dir,
        section_name="없는섹션",
        new_content="new",
    )
    assert result is False


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


def test_update_appends_learning_history(tmp_path):
    """update_profile_section appends to learning history."""
    company_dir = str(tmp_path / "comp")
    os.makedirs(company_dir)
    with open(os.path.join(company_dir, "profile.md"), "w") as f:
        f.write("## 문체\n- test\n\n## 학습 이력\n(아직 없음)\n")

    update_profile_section(
        company_dir=company_dir,
        section_name="문체",
        new_content="- 경어체",
        backup=False,
    )

    with open(os.path.join(company_dir, "profile.md")) as f:
        content = f.read()

    assert "auto_learner" in content
    assert "문체 섹션 업데이트" in content
