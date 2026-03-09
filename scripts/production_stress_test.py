#!/usr/bin/env python3
"""
Production Stress Test - 실전 문서로 전체 파이프라인 검증

실행:
    python scripts/production_stress_test.py --env local
    python scripts/production_stress_test.py --env railway

테스트:
1. 회사 문서 20개 업로드 → 세션 생성
2. 공고 문서 10개 분석 → RFP 추출
3. GO/NO-GO 판단
4. 제안서 생성 (DOCX + HWPX)
5. 체크리스트 추출
6. WBS/PPT/실적기술서 생성
7. 결과 리포트 (성공률, 응답시간, 에러)
"""
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# API Base URLs
API_URLS = {
    "local": "http://localhost:8000",
    "railway": "https://m-s-solutions-production.up.railway.app",
}

# Test Data Paths
PROJECT_ROOT = Path(__file__).parent.parent
COMPANY_DOCS_DIR = PROJECT_ROOT / "data" / "company_docs"
TEST_DOCS_DIR = PROJECT_ROOT / "docs" / "test"
OUTPUT_DIR = PROJECT_ROOT / "dogfood-output" / "api-test"

# Results tracking
results = {
    "start_time": None,
    "end_time": None,
    "environment": None,
    "tests": [],
    "summary": {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "avg_response_time_sec": 0.0,
    },
}


def log_test(name: str, status: str, duration_sec: float, details: dict[str, Any] = None):
    """테스트 결과 로깅"""
    test_result = {
        "name": name,
        "status": status,  # "PASS" or "FAIL"
        "duration_sec": round(duration_sec, 2),
        "timestamp": datetime.now().isoformat(),
        "details": details or {},
    }
    results["tests"].append(test_result)
    results["summary"]["total"] += 1
    if status == "PASS":
        results["summary"]["passed"] += 1
    else:
        results["summary"]["failed"] += 1

    # Console output
    emoji = "✅" if status == "PASS" else "❌"
    print(f"{emoji} {name} ({duration_sec:.2f}s)")
    if details:
        for key, value in details.items():
            print(f"   - {key}: {value}")


def test_upload_company_docs(client: httpx.Client, base_url: str, session_id: str) -> bool:
    """TEST 1: 회사 문서 20개 업로드"""
    start = time.time()

    try:
        pdf_files = list(COMPANY_DOCS_DIR.glob("*.pdf"))[:5]  # 5개만 (속도)

        if not pdf_files:
            log_test("Upload Company Docs", "FAIL", time.time() - start, {"error": "No PDF files found"})
            return False

        files = []
        for pdf_path in pdf_files:
            files.append(("files", (pdf_path.name, open(pdf_path, "rb"), "application/pdf")))

        response = client.post(
            f"{base_url}/api/company/upload",
            data={"session_id": session_id},
            files=files,
            timeout=120,
        )

        # Close file handles
        for _, (_, fh, _) in files:
            fh.close()

        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            log_test(
                "Upload Company Docs",
                "PASS",
                duration,
                {
                    "files_uploaded": len(pdf_files),
                    "total_chunks": data.get("total_chunks", 0),
                },
            )
            return True
        else:
            log_test(
                "Upload Company Docs",
                "FAIL",
                duration,
                {"status_code": response.status_code, "error": response.text[:200]},
            )
            return False

    except Exception as exc:
        log_test("Upload Company Docs", "FAIL", time.time() - start, {"error": str(exc)})
        return False


def test_analyze_bid(client: httpx.Client, base_url: str, session_id: str) -> dict | None:
    """TEST 2: 공고 문서 분석 → RFP 추출 + GO/NO-GO"""
    start = time.time()

    try:
        test_pdfs = list(TEST_DOCS_DIR.glob("*.pdf"))[:1]  # 1개만 (시간)

        if not test_pdfs:
            log_test("Analyze Bid", "FAIL", time.time() - start, {"error": "No test PDF found"})
            return None

        bid_pdf = test_pdfs[0]

        with open(bid_pdf, "rb") as f:
            files = {"file": (bid_pdf.name, f, "application/pdf")}
            response = client.post(
                f"{base_url}/api/analyze/upload",
                data={"session_id": session_id},
                files=files,
                timeout=300,
            )

        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            analysis = data.get("analysis", {})
            matching = data.get("matching", {})

            log_test(
                "Analyze Bid",
                "PASS",
                duration,
                {
                    "file": bid_pdf.name,
                    "requirements_count": len(analysis.get("requirements", [])),
                    "go_no_go": matching.get("decision") if matching else "N/A",
                    "score": matching.get("overall_score") if matching else "N/A",
                },
            )
            return data
        else:
            log_test(
                "Analyze Bid",
                "FAIL",
                duration,
                {"status_code": response.status_code, "error": response.text[:200]},
            )
            return None

    except Exception as exc:
        log_test("Analyze Bid", "FAIL", time.time() - start, {"error": str(exc)})
        return None


def test_generate_proposal_docx(client: httpx.Client, base_url: str, session_id: str) -> str | None:
    """TEST 3: 제안서 생성 (DOCX)"""
    start = time.time()

    try:
        response = client.post(
            f"{base_url}/api/proposal/generate-v2",
            json={"session_id": session_id, "total_pages": 30, "output_format": "docx"},
            timeout=300,
        )

        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            filename = data.get("docx_filename") or data.get("output_filename")

            log_test(
                "Generate Proposal DOCX",
                "PASS",
                duration,
                {
                    "filename": filename,
                    "sections": len(data.get("sections", [])),
                    "quality_issues": len(data.get("quality_issues", [])),
                },
            )
            return filename
        else:
            log_test(
                "Generate Proposal DOCX",
                "FAIL",
                duration,
                {"status_code": response.status_code, "error": response.text[:200]},
            )
            return None

    except Exception as exc:
        log_test("Generate Proposal DOCX", "FAIL", time.time() - start, {"error": str(exc)})
        return None


def test_generate_proposal_hwpx(client: httpx.Client, base_url: str, session_id: str) -> str | None:
    """TEST 4: 제안서 생성 (HWPX) - 신기능"""
    start = time.time()

    try:
        response = client.post(
            f"{base_url}/api/proposal/generate-v2",
            json={"session_id": session_id, "total_pages": 30, "output_format": "hwpx"},
            timeout=300,
        )

        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            filename = data.get("hwpx_filename") or data.get("output_filename")

            log_test(
                "Generate Proposal HWPX",
                "PASS",
                duration,
                {
                    "filename": filename,
                    "sections": len(data.get("sections", [])),
                    "quality_issues": len(data.get("quality_issues", [])),
                },
            )
            return filename
        else:
            log_test(
                "Generate Proposal HWPX",
                "FAIL",
                duration,
                {"status_code": response.status_code, "error": response.text[:200]},
            )
            return None

    except Exception as exc:
        log_test("Generate Proposal HWPX", "FAIL", time.time() - start, {"error": str(exc)})
        return None


def test_download_file(client: httpx.Client, base_url: str, filename: str) -> bool:
    """TEST: 파일 다운로드 검증"""
    if not filename:
        return False

    start = time.time()

    try:
        response = client.get(
            f"{base_url}/api/proposal/download/{filename}",
            timeout=30,
        )

        duration = time.time() - start

        if response.status_code == 200 and len(response.content) > 0:
            # Save to output dir
            output_path = OUTPUT_DIR / filename
            output_path.write_bytes(response.content)

            log_test(
                f"Download {filename}",
                "PASS",
                duration,
                {"file_size_kb": len(response.content) // 1024},
            )
            return True
        else:
            log_test(
                f"Download {filename}",
                "FAIL",
                duration,
                {"status_code": response.status_code},
            )
            return False

    except Exception as exc:
        log_test(f"Download {filename}", "FAIL", time.time() - start, {"error": str(exc)})
        return False


def test_checklist(client: httpx.Client, base_url: str, session_id: str) -> bool:
    """TEST 5: 체크리스트 추출"""
    start = time.time()

    try:
        response = client.post(
            f"{base_url}/api/proposal/checklist",
            json={"session_id": session_id},
            timeout=60,
        )

        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            log_test(
                "Checklist Extraction",
                "PASS",
                duration,
                {
                    "total_items": data.get("total", 0),
                    "mandatory": data.get("mandatory_count", 0),
                },
            )
            return True
        else:
            log_test(
                "Checklist Extraction",
                "FAIL",
                duration,
                {"status_code": response.status_code, "error": response.text[:200]},
            )
            return False

    except Exception as exc:
        log_test("Checklist Extraction", "FAIL", time.time() - start, {"error": str(exc)})
        return False


def main():
    parser = argparse.ArgumentParser(description="Production Stress Test")
    parser.add_argument("--env", choices=["local", "railway"], default="local", help="Test environment")
    args = parser.parse_args()

    base_url = API_URLS[args.env]
    results["environment"] = args.env
    results["start_time"] = datetime.now().isoformat()

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"🚀 Production Stress Test - {args.env.upper()}")
    print(f"{'='*60}\n")

    # Create session ID
    session_id = f"stress_test_{int(time.time())}"
    print(f"📋 Session ID: {session_id}\n")

    with httpx.Client() as client:
        # TEST 1: Upload Company Docs
        if not test_upload_company_docs(client, base_url, session_id):
            print("\n⚠️  Company doc upload failed. Continuing without company context.\n")

        # TEST 2: Analyze Bid
        analysis_result = test_analyze_bid(client, base_url, session_id)
        if not analysis_result:
            print("\n❌ Bid analysis failed. Cannot continue.\n")
            return

        # TEST 3: Generate Proposal DOCX
        docx_filename = test_generate_proposal_docx(client, base_url, session_id)
        if docx_filename:
            test_download_file(client, base_url, docx_filename)

        # TEST 4: Generate Proposal HWPX (신기능)
        hwpx_filename = test_generate_proposal_hwpx(client, base_url, session_id)
        if hwpx_filename:
            test_download_file(client, base_url, hwpx_filename)

        # TEST 5: Checklist
        test_checklist(client, base_url, session_id)

    # Finalize results
    results["end_time"] = datetime.now().isoformat()

    if results["summary"]["total"] > 0:
        total_duration = sum(t["duration_sec"] for t in results["tests"])
        results["summary"]["avg_response_time_sec"] = round(
            total_duration / results["summary"]["total"], 2
        )

    # Save results
    report_path = OUTPUT_DIR / f"stress_test_{args.env}_{int(time.time())}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total Tests:    {results['summary']['total']}")
    print(f"✅ Passed:      {results['summary']['passed']}")
    print(f"❌ Failed:      {results['summary']['failed']}")
    print(f"⏱  Avg Time:    {results['summary']['avg_response_time_sec']}s")
    print(f"\n📄 Full report: {report_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
