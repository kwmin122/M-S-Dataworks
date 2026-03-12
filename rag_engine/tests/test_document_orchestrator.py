"""Tests for unified document orchestrator."""
import pytest
from unittest.mock import patch, MagicMock, ANY
from pathlib import Path

from document_orchestrator import generate_document, DocumentResult


@pytest.fixture
def mock_rfx():
    return {
        "title": "치유농업 연구개발 종합계획 수립 연구용역",
        "full_text": "치유농업 효과성 검증 및 정책 방향 수립 기초연구",
        "evaluation_criteria": [],
    }


@pytest.fixture
def real_packs_dir():
    """Use the ACTUAL _default Guide Pack from data/company_packs/.

    This is the single source of truth for the domain-native section structure (research: 9장).
    If sections.json changes, this test automatically reflects it.
    Task 2 creates these files; this fixture reads them directly.
    """
    packs = Path(__file__).resolve().parent.parent.parent / "data" / "company_packs"
    assert (packs / "_default" / "pack.json").exists(), \
        "Guide Pack not found -- run Task 2 first"
    assert (packs / "_default" / "execution_plan" / "research" / "sections.json").exists(), \
        "Research sections.json not found -- run Task 2 first"
    return str(packs)


@pytest.fixture
def expected_section_count():
    """Load the actual section count from the real Guide Pack sections.json.

    Acceptance criteria are validated against this number, not a hardcoded constant.
    """
    sections_path = (
        Path(__file__).resolve().parent.parent.parent
        / "data" / "company_packs" / "_default"
        / "execution_plan" / "research" / "sections.json"
    )
    import json
    data = json.loads(sections_path.read_text(encoding="utf-8"))
    count = len(data["sections"])
    assert count >= 9, f"Research Guide Pack should have >= 9 sections, got {count}"
    return count


@pytest.fixture
def pack_dir(tmp_path):
    """Minimal 2-section pack for fast unit tests (pipeline wiring only).

    NOT used for 9-chapter acceptance -- use real_packs_dir for that.
    """
    import json
    default = tmp_path / "_default"
    default.mkdir()
    (default / "pack.json").write_text(json.dumps({
        "pack_id": "test", "company_id": "_default", "version": 1,
        "status": "active", "base_pack_ref": None,
    }))
    research = default / "execution_plan" / "research"
    research.mkdir(parents=True)
    (research / "sections.json").write_text(json.dumps({
        "document_type": "execution_plan", "domain_type": "research",
        "sections": [
            {"id": "s01", "name": "사업 이해", "level": 1, "weight": 0.5, "max_score": 15,
             "generation_target": {"min_chars": 100, "max_chars": 500, "token_budget": 500}},
            {"id": "s02", "name": "수행 전략", "level": 1, "weight": 0.5, "max_score": 20,
             "generation_target": {"min_chars": 100, "max_chars": 500, "token_budget": 500}},
        ],
    }))
    (research / "domain_dict.json").write_text(json.dumps({
        "domain_type": "research",
        "roles": [{"id": "pi", "name": "연구책임자", "grade": "특급"}],
        "phases": [{"id": "design", "name": "연구설계"}],
    }))
    (research / "boilerplate.json").write_text(json.dumps({"boilerplates": []}))
    return tmp_path


class TestDocumentOrchestrator:
    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_full_pipeline(self, mock_assemble, mock_schedule, mock_write, mock_detect,
                            mock_rfx, pack_dir, tmp_path):
        from phase2_models import DomainType, WbsTask, PersonnelAllocation
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "생성된 섹션 텍스트..."
        mock_schedule.return_value = (
            [WbsTask(phase="연구설계", task_name="계획", start_month=1, duration_months=2)],
            [PersonnelAllocation(role="연구책임자", total_man_months=2.0)],
            12,
        )

        result = generate_document(
            rfx_result=mock_rfx,
            doc_type="execution_plan",
            output_dir=str(tmp_path / "output"),
            packs_dir=str(pack_dir),
        )
        assert isinstance(result, DocumentResult)
        assert result.domain_type == "research"
        assert mock_write.call_count == 2  # s01, s02 from minimal pack_dir fixture
        mock_assemble.assert_called_once()

    @patch("document_orchestrator.detect_domain")
    def test_domain_detection_called(self, mock_detect, mock_rfx, pack_dir, tmp_path):
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH

        with patch("document_orchestrator._write_section_with_pack", return_value="text"):
            with patch("document_orchestrator.plan_schedule", return_value=([], [], 12)):
                with patch("document_orchestrator.assemble_docx"):
                    generate_document(
                        rfx_result=mock_rfx,
                        doc_type="execution_plan",
                        output_dir=str(tmp_path / "output"),
                        packs_dir=str(pack_dir),
                    )
        mock_detect.assert_called_once()

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_research_9chapter_structure(self, mock_assemble, mock_schedule, mock_write,
                                          mock_detect, mock_rfx, real_packs_dir,
                                          expected_section_count, tmp_path):
        """Acceptance A: research 9-chapter structure -- section_match_rate >= 0.875.

        Uses the REAL Guide Pack as the single source of truth.
        """
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "본 연구의 내용을 서술합니다. 발주기관 KOICA의 사업 이해. " * 10
        mock_schedule.return_value = ([], [], 12)

        result = generate_document(
            rfx_result=mock_rfx, doc_type="execution_plan",
            output_dir=str(tmp_path / "output"), packs_dir=real_packs_dir,
        )
        section_names = [name for name, _ in result.sections]

        # Load expected names + required flags from the same source of truth
        import json
        sections_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "company_packs" / "_default"
            / "execution_plan" / "research" / "sections.json"
        )
        raw_sections = json.loads(sections_path.read_text(encoding="utf-8"))["sections"]
        expected_names = [s["name"] for s in raw_sections]
        required_names = [s["name"] for s in raw_sections if s.get("required", True)]

        # 1. Count check: section_match_rate >= 0.875
        match_rate = len(section_names) / expected_section_count
        assert match_rate >= 0.875, (
            f"section_match_rate {match_rate:.3f} < 0.875 "
            f"({len(section_names)}/{expected_section_count} sections resolved)"
        )

        # 2. Required check: ALL required sections must be present
        missing_required = [n for n in required_names if n not in section_names]
        assert not missing_required, (
            f"Required sections missing: {missing_required}"
        )

        # 3. Identity check: every returned section name must exist in expected
        unexpected = [n for n in section_names if n not in expected_names]
        assert not unexpected, f"Unexpected section names: {unexpected}"

        # 4. Order check: returned sections preserve expected order (no reordering)
        expected_order = [n for n in expected_names if n in section_names]
        assert section_names == expected_order, (
            f"Section order mismatch.\n  Expected: {expected_order}\n  Got:      {section_names}"
        )

        assert result.domain_type == "research"

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_quality_no_length_violation(self, mock_assemble, mock_schedule, mock_write,
                                          mock_detect, mock_rfx, real_packs_dir, tmp_path):
        """Acceptance A: length_violation == 0 against real 9-section Pack.

        Each section has different min/max ranges, so return per-section text
        that fits within the target range using the section's generation_target.
        """
        from phase2_models import DomainType
        import json

        mock_detect.return_value = DomainType.RESEARCH
        mock_schedule.return_value = ([], [], 12)

        # Load sections to build per-section target text lengths
        sections_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "company_packs" / "_default"
            / "execution_plan" / "research" / "sections.json"
        )
        raw_sections = json.loads(sections_path.read_text(encoding="utf-8"))["sections"]
        # Build midpoint char count for each section
        base = "본 연구는 치유농업의 효과를 분석합니다. "  # 22 chars
        section_targets = {}
        for s in raw_sections:
            gt = s.get("generation_target", {})
            min_c = gt.get("min_chars", 1000)
            max_c = gt.get("max_chars", 5000)
            mid = (min_c + max_c) // 2
            section_targets[s["name"]] = mid

        def _make_text(*args, **kwargs):
            section = kwargs.get("section") or args[0]
            target = section_targets.get(section.name, 2000)
            repeats = max(1, target // len(base))
            return base * repeats

        mock_write.side_effect = _make_text

        result = generate_document(
            rfx_result=mock_rfx, doc_type="execution_plan",
            output_dir=str(tmp_path / "output"), packs_dir=real_packs_dir,
        )
        length_violations = [i for i in result.quality_issues if i.category == "length_violation"]
        assert len(length_violations) == 0, (
            f"length_violation found: {[(i.detail,) for i in length_violations]}"
        )

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_quality_no_blind_violation(self, mock_assemble, mock_schedule, mock_write,
                                         mock_detect, mock_rfx, real_packs_dir, tmp_path):
        """Acceptance A: blind_violation == 0 against real 9-section Pack."""
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "본 연구는 치유농업의 효과를 분석하고 정책을 수립합니다. " * 50
        mock_schedule.return_value = ([], [], 12)

        result = generate_document(
            rfx_result=mock_rfx, doc_type="execution_plan",
            output_dir=str(tmp_path / "output"), packs_dir=real_packs_dir,
        )
        blind_violations = [i for i in result.quality_issues if i.category == "blind_violation"]
        assert len(blind_violations) == 0, (
            f"blind_violation found: {[(i.detail,) for i in blind_violations]}"
        )


class TestCompanyContextPropagation:
    """Verify company context + company_name flow through to section writer and DOCX."""

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_company_context_passed_to_section_writer(
        self, mock_assemble, mock_schedule, mock_write, mock_detect,
        mock_rfx, pack_dir, tmp_path,
    ):
        """company_context string reaches _write_section_with_pack."""
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "텍스트"
        mock_schedule.return_value = ([], [], 12)

        generate_document(
            rfx_result=mock_rfx,
            doc_type="execution_plan",
            output_dir=str(tmp_path / "output"),
            packs_dir=str(pack_dir),
            company_context="## 회사 기본 정보\n회사명: 테스트주식회사",
        )

        # Every section_writer call should receive the company_context
        for call in mock_write.call_args_list:
            assert call.kwargs.get("company_context") == "## 회사 기본 정보\n회사명: 테스트주식회사"

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_company_name_passed_to_docx_assembler(
        self, mock_assemble, mock_schedule, mock_write, mock_detect,
        mock_rfx, pack_dir, tmp_path,
    ):
        """company_name (not company_context[:50]) reaches assemble_docx."""
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "텍스트"
        mock_schedule.return_value = ([], [], 12)

        generate_document(
            rfx_result=mock_rfx,
            doc_type="execution_plan",
            output_dir=str(tmp_path / "output"),
            packs_dir=str(pack_dir),
            company_name="테스트주식회사",
            company_context="## 회사 기본 정보\n회사명: 테스트주식회사\n인력: 50명",
        )

        mock_assemble.assert_called_once()
        assert mock_assemble.call_args.kwargs.get("company_name") == "테스트주식회사"

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_company_context_passed_to_schedule_planner(
        self, mock_assemble, mock_schedule, mock_write, mock_detect,
        mock_rfx, pack_dir, tmp_path,
    ):
        """company_context reaches plan_schedule for WBS task generation."""
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "텍스트"
        mock_schedule.return_value = ([], [], 12)

        generate_document(
            rfx_result=mock_rfx,
            doc_type="execution_plan",
            output_dir=str(tmp_path / "output"),
            packs_dir=str(pack_dir),
            company_context="특급기술사 5명 보유",
        )

        mock_schedule.assert_called_once()
        assert mock_schedule.call_args.kwargs.get("company_context") == "특급기술사 5명 보유"

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_empty_company_context_does_not_break(
        self, mock_assemble, mock_schedule, mock_write, mock_detect,
        mock_rfx, pack_dir, tmp_path,
    ):
        """Pipeline works correctly with empty company_context (no CompanyDB data)."""
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "텍스트"
        mock_schedule.return_value = ([], [], 12)

        result = generate_document(
            rfx_result=mock_rfx,
            doc_type="execution_plan",
            output_dir=str(tmp_path / "output"),
            packs_dir=str(pack_dir),
            company_context="",
            company_name="",
        )

        assert isinstance(result, DocumentResult)
        mock_assemble.assert_called_once()
        assert mock_assemble.call_args.kwargs.get("company_name") == ""

    @patch("document_orchestrator.detect_domain")
    @patch("document_orchestrator._write_section_with_pack")
    @patch("document_orchestrator.plan_schedule")
    @patch("document_orchestrator.assemble_docx")
    def test_company_id_selects_company_pack(
        self, mock_assemble, mock_schedule, mock_write, mock_detect,
        mock_rfx, pack_dir, tmp_path,
    ):
        """company_id is passed to PackManager for company-specific Pack selection."""
        from phase2_models import DomainType
        mock_detect.return_value = DomainType.RESEARCH
        mock_write.return_value = "텍스트"
        mock_schedule.return_value = ([], [], 12)

        # Non-existent company falls back to _default gracefully
        result = generate_document(
            rfx_result=mock_rfx,
            doc_type="execution_plan",
            output_dir=str(tmp_path / "output"),
            packs_dir=str(pack_dir),
            company_id="some_company",
        )
        # Should succeed with _default fallback
        assert isinstance(result, DocumentResult)
        assert result.domain_type == "research"
