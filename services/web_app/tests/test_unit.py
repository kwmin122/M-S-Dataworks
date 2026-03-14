"""Layer 1: Unit Tests — No DB, No I/O."""
from __future__ import annotations


# --- Enum + state transition ---
from services.web_app.db.models.base import DocType, ContentSchema


def test_doc_type_values():
    assert DocType.PROPOSAL == "proposal"
    assert len(DocType.ALL) == 5
    assert DocType.CHECKLIST in DocType.ALL


def test_content_schema_consistency():
    for dt in DocType.ALL:
        assert hasattr(ContentSchema, f"{dt.upper()}_V1")


# --- ACL hierarchy ---
from services.web_app.api.deps import _ACCESS_LEVELS


def test_access_level_hierarchy():
    assert _ACCESS_LEVELS["owner"] > _ACCESS_LEVELS["editor"]
    assert _ACCESS_LEVELS["editor"] > _ACCESS_LEVELS["reviewer"]
    assert _ACCESS_LEVELS["reviewer"] > _ACCESS_LEVELS["viewer"]


def test_all_levels_defined():
    for level in ("viewer", "reviewer", "approver", "editor", "owner"):
        assert level in _ACCESS_LEVELS


# --- cuid2 + S3 key ---
from services.web_app.db.models.base import new_cuid


def test_cuid_unique():
    ids = {new_cuid() for _ in range(100)}
    assert len(ids) == 100


# --- BidProject status transitions ---
_VALID_TRANSITIONS = {
    "draft": {"collecting_inputs", "analyzing"},
    "collecting_inputs": {"analyzing"},
    "analyzing": {"ready_for_generation"},
    "ready_for_generation": {"generating"},
    "generating": {"in_review", "ready_for_generation"},
    "in_review": {"changes_requested", "approved"},
    "changes_requested": {"in_review", "generating"},
    "approved": {"locked_for_submission"},
    "locked_for_submission": {"submitted"},
    "submitted": {"archived"},
}


def test_status_transitions_complete():
    """Every status except 'archived' has at least one valid transition."""
    for status in _VALID_TRANSITIONS:
        assert len(_VALID_TRANSITIONS[status]) >= 1
