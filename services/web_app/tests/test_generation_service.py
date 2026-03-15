"""Generation service tests — DocumentRun lifecycle. Requires PostgreSQL."""
from __future__ import annotations

import pytest
from services.web_app.db.models.org import Organization
from services.web_app.db.models.project import BidProject
from services.web_app.db.models.document import DocumentRun


@pytest.mark.asyncio
async def test_create_document_run(db_session):
    """Creates a DocumentRun with status=queued."""
    from services.web_app.services.generation_service import create_document_run

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트 사업")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session,
        org_id=org.id,
        project_id=project.id,
        doc_type="proposal",
        created_by="u1",
        params={"total_pages": 50},
    )
    assert run.status == "queued"
    assert run.doc_type == "proposal"


@pytest.mark.asyncio
async def test_complete_document_run(db_session):
    """Transitions DocumentRun to completed and creates DocumentRevision."""
    from services.web_app.services.generation_service import (
        create_document_run, complete_document_run,
    )

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session, org_id=org.id, project_id=project.id,
        doc_type="proposal", created_by="u1",
    )

    revision = await complete_document_run(
        db=db_session,
        run=run,
        content_json={"sections": [{"name": "개요", "text": "내용"}]},
        content_schema="proposal_sections_v1",
        quality_report={"issues": [], "total_issues": 0},
        output_files=[],
    )
    assert run.status == "completed"
    assert revision.content_schema == "proposal_sections_v1"
    assert revision.source == "ai_generated"


@pytest.mark.asyncio
async def test_fail_document_run(db_session):
    """Transitions DocumentRun to failed."""
    from services.web_app.services.generation_service import (
        create_document_run, fail_document_run,
    )

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session, org_id=org.id, project_id=project.id,
        doc_type="execution_plan", created_by="u1",
    )

    await fail_document_run(db=db_session, run=run, error="LLM timeout")
    assert run.status == "failed"
    assert run.error_message == "LLM timeout"
