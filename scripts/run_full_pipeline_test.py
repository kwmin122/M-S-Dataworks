#!/usr/bin/env python3
"""
전체 파이프라인 E2E 테스트 (정확도 중심)

공고→분석→GO/NO-GO→제안서→WBS→PPT→실적→체크리스트 전체 검증
"""
import asyncio
import aiohttp
import json
import time
import io
from pathlib import Path
from datetime import datetime
from typing import Dict
import sys

BASE_URL = "http://localhost:8000"
RAG_URL = "http://localhost:8001"
TIMEOUT = 180  # 각 단계 최대 3분

# 정확도 기준
ACCURACY_CRITERIA = {
    "go_no_go_score_tolerance": 15,  # ±15점 허용
    "min_proposal_pages": 10,  # 제안서 최소 10페이지
    "min_wbs_tasks": 5,  # WBS 최소 5개 태스크
    "min_ppt_slides": 10,  # PPT 최소 10개 슬라이드
    "min_checklist_items": 5,  # 체크리스트 최소 5개 항목
}


async def run_full_pipeline_test(scenario: Dict) -> Dict:
    """
    단일 시나리오 전체 파이프라인 테스트

    Steps:
    1. 회사 문서 업로드
    2. 공고 업로드 + RFP 분석 + GO/NO-GO
    3. 제안서 생성 (v2) [GO인 경우만]
    4. WBS 생성 [GO인 경우만]
    5. PPT 생성 [GO인 경우만]
    6. 실적기술서 생성 [GO인 경우만]
    7. 체크리스트

    Returns:
        전체 결과 dict
    """
    scenario_id = scenario['id']
    session_id = f"{scenario_id.lower()}_{int(time.time() * 1000)}"

    result = {
        "scenario_id": scenario_id,
        "company": scenario['company'],
        "match_type": scenario['match_type'],
        "steps": {},
        "accuracy": {},
        "overall_success": False,
        "total_duration_ms": 0
    }

    start_time = time.time()
    connector = aiohttp.TCPConnector()
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

            # Step 1: 회사 문서 업로드
            result["steps"]["step1_upload_company"] = await upload_company(session, scenario, session_id)

            # Step 2: 공고 업로드 + 분석 + GO/NO-GO
            result["steps"]["step2_analyze"] = await upload_and_analyze_bid(session, scenario, session_id)

            # GO인 경우에만 문서 생성
            analyze_step = result["steps"]["step2_analyze"]
            is_go = analyze_step.get("actual_result") == "GO"

            if is_go:
                # Step 3: 제안서 생성 (v2)
                result["steps"]["step3_proposal"] = await generate_proposal_v2(
                    session, scenario, session_id, analyze_step
                )

                # Step 4: WBS 생성
                result["steps"]["step4_wbs"] = await generate_wbs(
                    session, scenario, session_id,
                    result["steps"]["step3_proposal"]
                )

                # Step 5: PPT 생성
                result["steps"]["step5_ppt"] = await generate_ppt(
                    session, scenario, session_id,
                    result["steps"]["step3_proposal"]
                )

                # Step 6: 실적기술서 생성
                result["steps"]["step6_track_record"] = await generate_track_record(
                    session, scenario, session_id,
                    result["steps"]["step3_proposal"]
                )

            # Step 7: 체크리스트 (GO/NO-GO 무관)
            result["steps"]["step7_checklist"] = await get_checklist(
                session, scenario, session_id
            )

            # 정확도 계산
            result["accuracy"] = calculate_accuracy(result, scenario)
            result["overall_success"] = result["accuracy"]["overall_pass"]

    except Exception as e:
        result["error"] = str(e)
        result["overall_success"] = False

    finally:
        result["total_duration_ms"] = int((time.time() - start_time) * 1000)

    return result


async def upload_company(session: aiohttp.ClientSession, scenario: Dict, session_id: str) -> Dict:
    """Step 1: 회사 문서 업로드"""
    step_result = {"success": False, "duration_ms": 0}
    start = time.time()

    try:
        company_pdf = f"data/company_docs/{scenario['company']}_회사소개서.pdf"
        if not Path(company_pdf).exists():
            raise FileNotFoundError(f"회사 문서 없음: {company_pdf}")

        # Read file content and wrap in BytesIO for proper multipart upload
        with open(company_pdf, 'rb') as f:
            file_content = f.read()

        data = aiohttp.FormData()
        data.add_field('session_id', session_id)
        data.add_field('files', io.BytesIO(file_content),
                      filename='company.pdf',  # Simplified filename to avoid encoding issues
                      content_type='application/pdf')

        async with session.post(
            f"{BASE_URL}/api/company/upload",
            data=data,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Upload failed: {resp.status}, {text}")
            upload_result = await resp.json()

            step_result["success"] = True
            step_result["chunks"] = upload_result.get("added_chunks", 0)

    except Exception as e:
        step_result["error"] = str(e)
    finally:
        step_result["duration_ms"] = int((time.time() - start) * 1000)

    return step_result


async def upload_and_analyze_bid(session: aiohttp.ClientSession, scenario: Dict, session_id: str) -> Dict:
    """Step 2: 공고 업로드 + 분석 + GO/NO-GO (한 번에)"""
    step_result = {"success": False, "duration_ms": 0}
    start = time.time()

    try:
        bid_path = f"docs/test/{scenario['bid']}"
        if not Path(bid_path).exists():
            bid_path = f"docs/dummy/{scenario['bid']}"

        if not Path(bid_path).exists():
            raise FileNotFoundError(f"공고 파일 없음: {scenario['bid']}")

        # Read file content and wrap in BytesIO for proper multipart upload
        with open(bid_path, 'rb') as f:
            file_content = f.read()

        data = aiohttp.FormData()
        data.add_field('session_id', session_id)
        # Use simplified filename to avoid encoding issues with Korean characters
        filename = 'bid.pdf' if scenario['bid'].endswith('.pdf') else 'bid.hwp'
        data.add_field('file', io.BytesIO(file_content),
                      filename=filename,
                      content_type='application/pdf' if filename.endswith('.pdf') else 'application/octet-stream')

        async with session.post(
            f"{BASE_URL}/api/analyze/upload",
            data=data,
            timeout=aiohttp.ClientTimeout(total=180)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Analyze failed: {resp.status}, {text}")
            result = await resp.json()

            step_result["success"] = True

            # 매칭 결과 추출 (overall_score와 recommendation 사용)
            matching = result.get("matching")
            if matching:
                step_result["actual_score"] = matching.get("overall_score")
                recommendation = matching.get("recommendation", "UNKNOWN")
                # recommendation을 GO/NO-GO 형식으로 변환
                # "🟢 GO" 또는 "🔴 NO-GO" 형식 파싱
                if "GO" in recommendation and "NO-GO" not in recommendation:
                    step_result["actual_result"] = "GO"
                elif "NO-GO" in recommendation:
                    step_result["actual_result"] = "NO-GO"
                elif "추천" in recommendation or "권장" in recommendation or recommendation == "QUALIFIED":
                    step_result["actual_result"] = "GO"
                elif "불합격" in recommendation or "미달" in recommendation or recommendation == "NOT_QUALIFIED":
                    step_result["actual_result"] = "NO-GO"
                else:
                    step_result["actual_result"] = recommendation
            else:
                step_result["actual_score"] = None
                step_result["actual_result"] = "NO_COMPANY_DATA"

            step_result["expected_score"] = scenario["expected_score"]
            step_result["expected_result"] = scenario["expected_result"]

            # 정확도 검증
            if step_result["actual_score"]:
                score_diff = abs(step_result["actual_score"] - step_result["expected_score"])
                step_result["score_diff"] = score_diff
                step_result["score_accurate"] = score_diff <= ACCURACY_CRITERIA["go_no_go_score_tolerance"]
            else:
                step_result["score_accurate"] = False

            step_result["result_match"] = (step_result["actual_result"] == step_result["expected_result"])

    except Exception as e:
        step_result["error"] = str(e)
    finally:
        step_result["duration_ms"] = int((time.time() - start) * 1000)

    return step_result


async def generate_proposal_v2(session: aiohttp.ClientSession, scenario: Dict, session_id: str, analyze_result: Dict) -> Dict:
    """Step 3: 제안서 생성 (v2)"""
    step_result = {"success": False, "duration_ms": 0, "skipped": False}
    start = time.time()

    # NO-GO인 경우 스킵
    if analyze_result.get("actual_result") != "GO":
        step_result["skipped"] = True
        step_result["reason"] = "NO-GO 판정으로 제안서 생성 스킵"
        return step_result

    try:
        async with session.post(
            f"{BASE_URL}/api/proposal/generate-v2",
            json={"session_id": session_id, "total_pages": 80},
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Proposal generation failed: {resp.status}, {text}")
            result = await resp.json()

            step_result["success"] = True
            step_result["file_generated"] = result.get("ok", False)
            step_result["filename"] = result.get("docx_filename", "")
            step_result["pages"] = result.get("total_pages", 0)
            step_result["blind_violations"] = result.get("blind_violations_count", 0)
            step_result["page_accurate"] = step_result["pages"] >= ACCURACY_CRITERIA["min_proposal_pages"]

    except Exception as e:
        step_result["error"] = str(e)
    finally:
        step_result["duration_ms"] = int((time.time() - start) * 1000)

    return step_result


async def generate_wbs(session: aiohttp.ClientSession, scenario: Dict, session_id: str, proposal_result: Dict) -> Dict:
    """Step 4: WBS 생성"""
    step_result = {"success": False, "duration_ms": 0, "skipped": False}
    start = time.time()

    if proposal_result.get("skipped"):
        step_result["skipped"] = True
        return step_result

    try:
        async with session.post(
            f"{BASE_URL}/api/proposal/generate-wbs",
            json={"session_id": session_id, "methodology": ""},
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"WBS generation failed: {resp.status}, {text}")
            result = await resp.json()

            step_result["success"] = True
            step_result["file_generated"] = result.get("ok", False)
            step_result["tasks"] = result.get("task_count", 0)
            step_result["task_count_accurate"] = step_result["tasks"] >= ACCURACY_CRITERIA["min_wbs_tasks"]

    except Exception as e:
        step_result["error"] = str(e)
    finally:
        step_result["duration_ms"] = int((time.time() - start) * 1000)

    return step_result


async def generate_ppt(session: aiohttp.ClientSession, scenario: Dict, session_id: str, proposal_result: Dict) -> Dict:
    """Step 5: PPT 생성"""
    step_result = {"success": False, "duration_ms": 0, "skipped": False}
    start = time.time()

    if proposal_result.get("skipped"):
        step_result["skipped"] = True
        return step_result

    try:
        async with session.post(
            f"{BASE_URL}/api/proposal/generate-ppt",
            json={"session_id": session_id, "duration_min": 30, "qna_count": 10},
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"PPT generation failed: {resp.status}, {text}")
            result = await resp.json()

            step_result["success"] = True
            step_result["file_generated"] = result.get("ok", False)
            step_result["slides"] = result.get("slide_count", 0)
            step_result["slide_count_accurate"] = step_result["slides"] >= ACCURACY_CRITERIA["min_ppt_slides"]

    except Exception as e:
        step_result["error"] = str(e)
    finally:
        step_result["duration_ms"] = int((time.time() - start) * 1000)

    return step_result


async def generate_track_record(session: aiohttp.ClientSession, scenario: Dict, session_id: str, proposal_result: Dict) -> Dict:
    """Step 6: 실적기술서 생성"""
    step_result = {"success": False, "duration_ms": 0, "skipped": False}
    start = time.time()

    if proposal_result.get("skipped"):
        step_result["skipped"] = True
        return step_result

    try:
        async with session.post(
            f"{BASE_URL}/api/proposal/generate-track-record",
            json={"session_id": session_id},
            timeout=aiohttp.ClientTimeout(total=180)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Track record generation failed: {resp.status}, {text}")
            result = await resp.json()

            step_result["success"] = True
            step_result["file_generated"] = result.get("ok", False)
            step_result["matched_records"] = result.get("matched_count", 0)

    except Exception as e:
        step_result["error"] = str(e)
    finally:
        step_result["duration_ms"] = int((time.time() - start) * 1000)

    return step_result


async def get_checklist(session: aiohttp.ClientSession, scenario: Dict, session_id: str) -> Dict:
    """Step 7: 체크리스트"""
    step_result = {"success": False, "duration_ms": 0}
    start = time.time()

    try:
        async with session.post(
            f"{BASE_URL}/api/proposal/checklist",
            json={"session_id": session_id},
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Checklist extraction failed: {resp.status}, {text}")
            result = await resp.json()

            step_result["success"] = True
            step_result["items"] = len(result.get("items", []))  # 'items' 키 사용
            step_result["item_count_accurate"] = step_result["items"] >= ACCURACY_CRITERIA["min_checklist_items"]

    except Exception as e:
        step_result["error"] = str(e)
    finally:
        step_result["duration_ms"] = int((time.time() - start) * 1000)

    return step_result


def calculate_accuracy(result: Dict, scenario: Dict) -> Dict:
    """정확도 계산"""
    accuracy = {
        "go_no_go_accurate": False,
        "proposal_accurate": False,
        "wbs_accurate": False,
        "ppt_accurate": False,
        "checklist_accurate": False,
        "overall_pass": False,
        "accuracy_score": 0.0
    }

    steps = result.get("steps", {})

    # GO/NO-GO 정확도
    analyze = steps.get("step2_analyze", {})
    if analyze.get("success"):
        accuracy["go_no_go_accurate"] = (
            analyze.get("score_accurate", False) and
            analyze.get("result_match", False)
        )

    # 제안서 정확도
    proposal = steps.get("step3_proposal", {})
    if not proposal.get("skipped") and proposal.get("success"):
        accuracy["proposal_accurate"] = proposal.get("page_accurate", False)
    elif proposal.get("skipped"):
        accuracy["proposal_accurate"] = True  # NO-GO는 생성 안 함이 정상

    # WBS 정확도
    wbs = steps.get("step4_wbs", {})
    if not wbs.get("skipped") and wbs.get("success"):
        accuracy["wbs_accurate"] = wbs.get("task_count_accurate", False)
    elif wbs.get("skipped"):
        accuracy["wbs_accurate"] = True

    # PPT 정확도
    ppt = steps.get("step5_ppt", {})
    if not ppt.get("skipped") and ppt.get("success"):
        accuracy["ppt_accurate"] = ppt.get("slide_count_accurate", False)
    elif ppt.get("skipped"):
        accuracy["ppt_accurate"] = True

    # 체크리스트 정확도
    checklist = steps.get("step7_checklist", {})
    if checklist.get("success"):
        accuracy["checklist_accurate"] = checklist.get("item_count_accurate", False)

    # 전체 정확도 점수
    accurate_count = sum([
        accuracy["go_no_go_accurate"],
        accuracy["proposal_accurate"],
        accuracy["wbs_accurate"],
        accuracy["ppt_accurate"],
        accuracy["checklist_accurate"]
    ])

    accuracy["accuracy_score"] = (accurate_count / 5.0) * 100
    accuracy["overall_pass"] = accuracy["accuracy_score"] >= 80.0  # 80% 이상 통과

    return accuracy


def print_results(results: list):
    """결과 출력 (정확도 중심)"""
    print("\n" + "=" * 120)
    print("전체 파이프라인 E2E 테스트 결과 (정확도 중심)")
    print("=" * 120)

    total = len(results)
    passed = sum(1 for r in results if r.get("overall_success"))

    print(f"\n📊 전체 통계:")
    print(f"  - 총 시나리오: {total}개")
    print(f"  - 통과: {passed}개")
    print(f"  - 실패: {total - passed}개")
    print(f"  - 성공률: {passed / total * 100:.1f}%")

    # 정확도 통계
    avg_accuracy = sum(r.get("accuracy", {}).get("accuracy_score", 0) for r in results) / total
    print(f"  - 평균 정확도: {avg_accuracy:.1f}%")

    print("\n" + "-" * 120)
    print(f"{'ID':<10} {'회사':<18} {'타입':<8} {'GO/NO-GO':<12} {'제안서':<10} {'WBS':<8} {'PPT':<8} {'체크리스트':<12} {'정확도':<10} {'상태':<10}")
    print("-" * 120)

    for r in results:
        sid = r['scenario_id']
        company = r.get('company', 'N/A')[:16]
        match_type = r.get('match_type', 'N/A')

        acc = r.get('accuracy', {})
        go_no_go = "✅" if acc.get('go_no_go_accurate') else "❌"
        proposal = "✅" if acc.get('proposal_accurate') else "❌"
        wbs = "✅" if acc.get('wbs_accurate') else "❌"
        ppt = "✅" if acc.get('ppt_accurate') else "❌"
        checklist = "✅" if acc.get('checklist_accurate') else "❌"
        accuracy_score = f"{acc.get('accuracy_score', 0):.1f}%"

        status = "✅ PASS" if r.get('overall_success') else "❌ FAIL"

        print(f"{sid:<10} {company:<18} {match_type:<8} {go_no_go:<12} {proposal:<10} {wbs:<8} {ppt:<8} {checklist:<12} {accuracy_score:<10} {status:<10}")

    print("-" * 120)

    # 상세 오류
    failed = [r for r in results if not r.get('overall_success')]
    if failed:
        print(f"\n❌ 실패 시나리오 상세 ({len(failed)}개):")
        for r in failed:
            print(f"\n  [{r['scenario_id']}] {r.get('company')}:")
            for step_name, step_data in r.get('steps', {}).items():
                if not step_data.get('success') and not step_data.get('skipped'):
                    error = step_data.get('error', 'Unknown error')
                    print(f"    - {step_name}: {error}")

    print("\n" + "=" * 120)

    # JSON 저장
    output_file = f"full_pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 상세 결과 저장: {output_file}")


# 테스트 시나리오 (샘플 3개)
TEST_SCENARIOS = [
    {
        "id": "TS-001",
        "company": "삼성SDS",
        "company_id": "company_001",
        "bid": "입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf",
        "expected_score": 95,
        "expected_result": "GO",
        "match_type": "HIGH"
    },
    {
        "id": "TS-002",
        "company": "정밀기계공업",
        "company_id": "company_007",
        "bid": "입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf",
        "expected_score": 45,
        "expected_result": "NO-GO",
        "match_type": "LOW"
    },
    {
        "id": "TS-003",
        "company": "더존비즈온",
        "company_id": "company_011",
        "bid": "선관위_입찰공고서 SW사업(국가(긴급)+1468+6146+조평(5억미만+온서)+공동+차등).pdf",
        "expected_score": 88,
        "expected_result": "GO",
        "match_type": "HIGH"
    }
]


async def main():
    """메인 실행"""
    print("=" * 120)
    print("🚀 전체 파이프라인 E2E 테스트 시작")
    print("=" * 120)
    print(f"\n설정:")
    print(f"  - 총 시나리오: {len(TEST_SCENARIOS)}개")
    print(f"  - 백엔드: {BASE_URL}")
    print(f"  - RAG Engine: {RAG_URL}")
    print(f"  - 정확도 기준: GO/NO-GO ±{ACCURACY_CRITERIA['go_no_go_score_tolerance']}점, 문서 생성 확인")

    print("\n⏳ 테스트 실행 중...\n")

    start_time = time.time()

    # 병렬 실행
    tasks = [run_full_pipeline_test(scenario) for scenario in TEST_SCENARIOS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Exception 처리
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "scenario_id": TEST_SCENARIOS[i]['id'],
                "overall_success": False,
                "error": str(result)
            })
        else:
            processed_results.append(result)

    total_time = time.time() - start_time

    print(f"\n⏱️  총 소요 시간: {total_time:.2f}초")

    # 결과 출력
    print_results(processed_results)


if __name__ == "__main__":
    asyncio.run(main())
