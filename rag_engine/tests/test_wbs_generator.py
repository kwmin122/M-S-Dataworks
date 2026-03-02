"""Tests for wbs_generator.py."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from phase2_models import WbsTask, PersonnelAllocation
from wbs_generator import generate_wbs_xlsx, generate_gantt_chart, generate_wbs_docx


def _sample_tasks():
    return [
        WbsTask(
            phase="착수",
            task_name="사업 착수 보고",
            start_month=1,
            duration_months=1,
            deliverables=["착수보고서"],
            responsible_role="PM",
            man_months=1.0,
        ),
        WbsTask(
            phase="분석",
            task_name="요구사항 분석",
            start_month=2,
            duration_months=2,
            deliverables=["요구사항정의서"],
            responsible_role="PL",
            man_months=2.0,
        ),
        WbsTask(
            phase="설계",
            task_name="아키텍처 설계",
            start_month=3,
            duration_months=2,
            deliverables=["설계서"],
            responsible_role="PL",
            man_months=2.0,
        ),
        WbsTask(
            phase="구현",
            task_name="기능 개발",
            start_month=4,
            duration_months=3,
            deliverables=["소스코드"],
            responsible_role="개발자",
            man_months=4.0,
        ),
    ]


def _sample_personnel():
    return [
        PersonnelAllocation(
            role="PM",
            grade="특급",
            total_man_months=2.0,
            monthly_allocation=[0.5, 0.3, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2],
        ),
        PersonnelAllocation(
            role="PL",
            grade="고급",
            total_man_months=4.0,
            monthly_allocation=[0.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.3, 0.2],
        ),
        PersonnelAllocation(
            role="개발자",
            grade="중급",
            total_man_months=4.0,
            monthly_allocation=[0.0, 0.0, 0.0, 1.3, 1.3, 1.3, 0.0, 0.0],
        ),
    ]


def test_generate_wbs_xlsx():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "wbs.xlsx")
        result = generate_wbs_xlsx(
            tasks=_sample_tasks(),
            personnel=_sample_personnel(),
            title="테스트 사업",
            total_months=8,
            output_path=path,
        )
        assert os.path.isfile(result)
        assert os.path.getsize(result) > 0


def test_generate_gantt_chart():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "gantt.png")
        result = generate_gantt_chart(
            tasks=_sample_tasks(),
            total_months=8,
            output_path=path,
        )
        assert os.path.isfile(result)
        assert os.path.getsize(result) > 0


def test_generate_wbs_docx_without_gantt():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "wbs.docx")
        result = generate_wbs_docx(
            tasks=_sample_tasks(),
            personnel=_sample_personnel(),
            title="테스트 수행계획서",
            total_months=8,
            methodology_name="waterfall",
            output_path=path,
        )
        assert os.path.isfile(result)


def test_generate_wbs_docx_with_gantt():
    with tempfile.TemporaryDirectory() as tmpdir:
        gantt_path = os.path.join(tmpdir, "gantt.png")
        generate_gantt_chart(_sample_tasks(), 8, gantt_path)

        docx_path = os.path.join(tmpdir, "wbs.docx")
        result = generate_wbs_docx(
            tasks=_sample_tasks(),
            personnel=_sample_personnel(),
            title="테스트 수행계획서",
            total_months=8,
            methodology_name="waterfall",
            output_path=docx_path,
            gantt_path=gantt_path,
        )
        assert os.path.isfile(result)
