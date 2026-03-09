#!/usr/bin/env python3
"""
병렬 E2E 테스트 실행기 (딥러닝 배치 학습 스타일)

20개 회사 더미 데이터 × 13개 공고 = 다양한 시나리오 병렬 검증
"""
import asyncio
import aiohttp
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import sys

# 테스트 시나리오 정의 (TEST_SCENARIOS.md 기반)
SCENARIOS = [
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
        "company": "제조기업 A",
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
    },
    {
        "id": "TS-004",
        "company": "컨설팅사 A",
        "company_id": "company_005",
        "bid": "(공고문) 제2차 치유농업 연구개발 및 육성을 위한 종합계획(27-31) 수립 연구용역.pdf",
        "expected_score": 82,
        "expected_result": "GO",
        "match_type": "MEDIUM"
    },
    {
        "id": "TS-005",
        "company": "현대건설",
        "company_id": "company_003",
        "bid": "입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf",
        "expected_score": 50,
        "expected_result": "NO-GO",
        "match_type": "LOW"
    },
    {
        "id": "TS-006",
        "company": "보안전문 A",
        "company_id": "company_018",
        "bid": "공고문-CCTV 감시 시스템 구축 및 유지보수 관리 운영.hwpx",
        "expected_score": 92,
        "expected_result": "GO",
        "match_type": "HIGH"
    },
    {
        "id": "TS-007",
        "company": "시스템통합 A",
        "company_id": "company_016",
        "bid": "[공고문] [9권역]학교 유무선 네트워크 개선 3차 정보통신공사 감리용역.hwp",
        "expected_score": 90,
        "expected_result": "GO",
        "match_type": "HIGH"
    },
    {
        "id": "TS-008",
        "company": "연구기업 A",
        "company_id": "company_009",
        "bid": "(공고문) 제2차 치유농업 연구개발 및 육성을 위한 종합계획(27-31) 수립 연구용역.pdf",
        "expected_score": 85,
        "expected_result": "GO",
        "match_type": "MEDIUM"
    },
    {
        "id": "TS-009",
        "company": "솔루션기업 B",
        "company_id": "company_015",
        "bid": "입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf",
        "expected_score": 87,
        "expected_result": "GO",
        "match_type": "MEDIUM"
    },
    {
        "id": "TS-010",
        "company": "IT서비스 C",
        "company_id": "company_020",
        "bid": "1. 입찰공고서(공고번호_R26BK01265177-000, 봉사단교육체계DX).hwp",
        "expected_score": 89,
        "expected_result": "GO",
        "match_type": "MEDIUM"
    }
]

BASE_URL = "http://localhost:8000"
BATCH_SIZE = 5  # 동시 실행 배치 크기 (딥러닝 배치와 유사)
TIMEOUT = 60  # 각 API 호출 타임아웃 (초)


async def run_scenario(session: aiohttp.ClientSession, scenario: Dict) -> Dict:
    """
    단일 시나리오 비동기 실행

    Args:
        session: aiohttp 세션
        scenario: 시나리오 정의

    Returns:
        결과 dict (scenario_id, success, score, result, error)
    """
    scenario_id = scenario['id']
    session_id = f"{scenario_id.lower()}_{int(time.time() * 1000)}"

    result = {
        "scenario_id": scenario_id,
        "company": scenario['company'],
        "match_type": scenario['match_type'],
        "expected_score": scenario['expected_score'],
        "expected_result": scenario['expected_result'],
        "actual_score": None,
        "actual_result": None,
        "success": False,
        "error": None,
        "duration_ms": 0
    }

    start_time = time.time()

    try:
        # Step 1: 공고 업로드
        bid_path = f"docs/test/{scenario['bid']}"
        if not Path(bid_path).exists():
            bid_path = f"docs/dummy/{scenario['bid']}"

        if not Path(bid_path).exists():
            raise FileNotFoundError(f"공고 파일 없음: {scenario['bid']}")

        with open(bid_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=scenario['bid'])

            async with session.post(
                f"{BASE_URL}/api/upload_target?session_id={session_id}",
                data=data,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"공고 업로드 실패: {resp.status}")
                upload_result = await resp.json()

        # Step 2: 회사 문서 업로드
        company_pdf = f"data/company_docs/{scenario['company']}_회사소개서.pdf"
        if not Path(company_pdf).exists():
            raise FileNotFoundError(f"회사 문서 없음: {company_pdf}")

        with open(company_pdf, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=f"{scenario['company']}_회사소개서.pdf")

            async with session.post(
                f"{BASE_URL}/api/upload_company?session_id={session_id}",
                data=data,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"회사 문서 업로드 실패: {resp.status}")
                company_result = await resp.json()

        # Step 3: 분석 실행
        async with session.post(
            f"{BASE_URL}/api/analyze?session_id={session_id}",
            timeout=aiohttp.ClientTimeout(total=TIMEOUT * 3)  # 분석은 더 오래 걸림
        ) as resp:
            if resp.status != 200:
                raise Exception(f"분석 실패: {resp.status}")
            analyze_result = await resp.json()

        # 결과 파싱
        actual_score = analyze_result.get('go_no_go_score')
        actual_result = analyze_result.get('go_no_go_result', 'UNKNOWN')

        result['actual_score'] = actual_score
        result['actual_result'] = actual_result
        result['success'] = True

        # 검증
        score_diff = abs(actual_score - scenario['expected_score']) if actual_score else 999
        result['score_diff'] = score_diff
        result['result_match'] = (actual_result == scenario['expected_result'])

    except Exception as e:
        result['error'] = str(e)

    finally:
        result['duration_ms'] = int((time.time() - start_time) * 1000)

    return result


async def run_batch(scenarios: List[Dict]) -> List[Dict]:
    """
    시나리오 배치 병렬 실행 (딥러닝 배치 학습 스타일)

    Args:
        scenarios: 시나리오 리스트

    Returns:
        결과 리스트
    """
    connector = aiohttp.TCPConnector(limit=BATCH_SIZE)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT * 5)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [run_scenario(session, scenario) for scenario in scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Exception을 dict로 변환
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "scenario_id": scenarios[i]['id'],
                    "success": False,
                    "error": str(result),
                    "duration_ms": 0
                })
            else:
                processed_results.append(result)

        return processed_results


def print_results(results: List[Dict]):
    """결과 출력 (예쁘게)"""
    print("\n" + "=" * 100)
    print("병렬 E2E 테스트 결과 (딥러닝 배치 학습 스타일)")
    print("=" * 100)

    total = len(results)
    success_count = sum(1 for r in results if r['success'])

    print(f"\n📊 전체 통계:")
    print(f"  - 총 시나리오: {total}개")
    print(f"  - 성공: {success_count}개")
    print(f"  - 실패: {total - success_count}개")
    print(f"  - 성공률: {success_count / total * 100:.1f}%")

    # 매치 타입별 통계
    high_match = [r for r in results if r.get('match_type') == 'HIGH']
    medium_match = [r for r in results if r.get('match_type') == 'MEDIUM']
    low_match = [r for r in results if r.get('match_type') == 'LOW']

    print(f"\n📈 매치 타입별:")
    print(f"  - HIGH MATCH: {len(high_match)}개 (평균 점수: {sum(r.get('actual_score', 0) for r in high_match if r.get('actual_score')) / max(len([r for r in high_match if r.get('actual_score')]), 1):.1f})")
    print(f"  - MEDIUM MATCH: {len(medium_match)}개 (평균 점수: {sum(r.get('actual_score', 0) for r in medium_match if r.get('actual_score')) / max(len([r for r in medium_match if r.get('actual_score')]), 1):.1f})")
    print(f"  - LOW MATCH: {len(low_match)}개 (평균 점수: {sum(r.get('actual_score', 0) for r in low_match if r.get('actual_score')) / max(len([r for r in low_match if r.get('actual_score')]), 1):.1f})")

    print("\n" + "-" * 100)
    print(f"{'ID':<8} {'회사':<20} {'타입':<8} {'예상점수':<10} {'실제점수':<10} {'결과':<10} {'소요시간':<12} {'상태':<10}")
    print("-" * 100)

    for r in results:
        scenario_id = r['scenario_id']
        company = r.get('company', 'N/A')[:18]
        match_type = r.get('match_type', 'N/A')
        expected = r.get('expected_score', 0)
        actual = r.get('actual_score', 'N/A')
        result_str = r.get('actual_result', 'N/A')
        duration = r['duration_ms']
        status = "✅ PASS" if r['success'] else "❌ FAIL"

        if r['success']:
            score_diff = r.get('score_diff', 999)
            result_match = r.get('result_match', False)

            # 점수 오차 ±10점, 결과 일치 시 PASS
            if score_diff <= 10 and result_match:
                status = "✅ PASS"
            elif score_diff <= 20:
                status = "⚠️  WARN"
            else:
                status = "❌ FAIL"

        print(f"{scenario_id:<8} {company:<20} {match_type:<8} {expected:<10} {str(actual):<10} {result_str:<10} {duration:<12}ms {status:<10}")

    print("-" * 100)

    # 실패한 시나리오 상세 출력
    failed = [r for r in results if not r['success']]
    if failed:
        print(f"\n❌ 실패한 시나리오 ({len(failed)}개):")
        for r in failed:
            print(f"  - {r['scenario_id']}: {r.get('error', 'Unknown error')}")

    print("\n" + "=" * 100)

    # JSON 결과 저장
    output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 상세 결과 저장: {output_file}")


async def main():
    """메인 실행 함수"""
    print("=" * 100)
    print("🚀 병렬 E2E 테스트 시작 (딥러닝 배치 학습 스타일)")
    print("=" * 100)
    print(f"\n설정:")
    print(f"  - 총 시나리오: {len(SCENARIOS)}개")
    print(f"  - 배치 크기: {BATCH_SIZE} (동시 실행)")
    print(f"  - 백엔드 URL: {BASE_URL}")
    print(f"  - 타임아웃: {TIMEOUT}초")

    # 백엔드 Health Check
    try:
        connector = aiohttp.TCPConnector()
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    print(f"\n❌ 백엔드 응답 없음 (status: {resp.status})")
                    print("   백엔드 실행 후 다시 시도하세요: python services/web_app/main.py")
                    sys.exit(1)
    except Exception as e:
        print(f"\n❌ 백엔드 연결 실패: {e}")
        print("   백엔드 실행 후 다시 시도하세요: python services/web_app/main.py")
        sys.exit(1)

    print("\n✅ 백엔드 연결 확인 완료")
    print("\n⏳ 테스트 실행 중...")

    start_time = time.time()

    # 배치 병렬 실행
    results = await run_batch(SCENARIOS)

    total_time = time.time() - start_time

    print(f"\n⏱️  총 소요 시간: {total_time:.2f}초")
    print(f"   평균 시나리오당: {total_time / len(SCENARIOS):.2f}초")

    # 결과 출력
    print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
