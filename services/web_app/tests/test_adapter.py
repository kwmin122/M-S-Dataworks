"""Session Adapter tests — both structural and integration."""
from __future__ import annotations

import pytest
from services.web_app.api.adapter import SessionAdapter


def test_adapter_class_exists():
    assert hasattr(SessionAdapter, "get_or_create_project")
    assert hasattr(SessionAdapter, "save_analysis")
    assert hasattr(SessionAdapter, "get_analysis")


@pytest.mark.asyncio
async def test_adapter_creates_project_on_first_call(db_session):
    adapter = SessionAdapter(db_session)
    project = await adapter.get_or_create_project(
        session_id="sess_001",
        username="testuser",
        title="XX기관 사업",
    )
    assert project.id is not None
    assert project.title == "XX기관 사업"
    assert project.legacy_session_id == "sess_001"
    assert project.org_id


@pytest.mark.asyncio
async def test_adapter_returns_same_project_for_same_session(db_session):
    adapter = SessionAdapter(db_session)
    p1 = await adapter.get_or_create_project("sess_001", "testuser")
    p2 = await adapter.get_or_create_project("sess_001", "testuser")
    assert p1.id == p2.id


@pytest.mark.asyncio
async def test_adapter_save_and_get_analysis(db_session):
    adapter = SessionAdapter(db_session)
    project = await adapter.get_or_create_project("sess_002", "testuser")

    analysis = {"title": "테스트 사업", "requirements": [{"category": "기술", "description": "웹 시스템"}]}
    snapshot = await adapter.save_analysis(
        project_id=project.id,
        org_id=project.org_id,
        analysis_json=analysis,
        summary_md="## 사업개요\n테스트",
        username="testuser",
    )
    assert snapshot.version == 1
    assert snapshot.is_active is True

    fetched = await adapter.get_analysis(project.id)
    assert fetched is not None
    assert fetched["analysis_json"]["title"] == "테스트 사업"


@pytest.mark.asyncio
async def test_adapter_analysis_versioning(db_session):
    adapter = SessionAdapter(db_session)
    project = await adapter.get_or_create_project("sess_003", "testuser")

    s1 = await adapter.save_analysis(project.id, project.org_id, {"v": 1})
    assert s1.version == 1

    s2 = await adapter.save_analysis(project.id, project.org_id, {"v": 2})
    assert s2.version == 2

    fetched = await adapter.get_analysis(project.id)
    assert fetched["analysis_json"]["v"] == 2
