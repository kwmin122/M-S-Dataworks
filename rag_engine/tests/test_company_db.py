from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from company_db import CompanyDB, CompanyCapabilityProfile, TrackRecord, Personnel


@pytest.fixture
def db(tmp_path):
    return CompanyDB(persist_directory=str(tmp_path / "company"))


def test_add_and_search_track_record(db):
    record = TrackRecord(
        project_name="클라우드 마이그레이션",
        client="과학기술정보통신부",
        period="2024.03 ~ 2024.12",
        amount=5.0,
        description="레거시 시스템을 AWS 클라우드로 전환",
        technologies=["AWS", "Docker", "Kubernetes"],
        outcome="99.9% 가용성 달성",
    )
    doc_id = db.add_track_record(record)
    assert doc_id.startswith("tr_")
    assert db.count() == 1

    results = db.search_similar_projects("클라우드 전환 프로젝트")
    assert len(results) >= 1
    assert "클라우드" in results[0]["text"]


def test_add_and_search_personnel(db):
    person = Personnel(
        name="김철수",
        role="PM",
        experience_years=15,
        certifications=["PMP", "정보관리기술사"],
        key_projects=["국세청 차세대", "건보공단 클라우드"],
        specialties=["프로젝트관리", "클라우드"],
    )
    doc_id = db.add_personnel(person)
    assert doc_id.startswith("ps_")

    results = db.find_matching_personnel("PM 경력 10년 이상 클라우드")
    assert len(results) >= 1
    assert "김철수" in results[0]["text"]


def test_save_and_load_profile(db, tmp_path):
    profile = CompanyCapabilityProfile(
        name="테스트기업",
        registration_number="123-45-67890",
        licenses=["소프트웨어사업자"],
        capital=10.0,
        employee_count=50,
    )
    db.save_profile(profile)
    loaded = db.load_profile()
    assert loaded is not None
    assert loaded.name == "테스트기업"
    assert loaded.capital == 10.0


def test_load_profile_missing(db):
    result = db.load_profile()
    assert result is None
