#!/usr/bin/env python3
"""A/B 테스트: V1 vs V2 프롬프트 품질 비교.

동일 섹션(사업이해도)을 V1 프롬프트와 V2 프롬프트로 생성하고,
평가 루브릭으로 자동 채점합니다.
"""
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

# ── 더미 데이터 ──

DUMMY_RFP = """
[사업명] 선거기록관 확장형 영구기록관리시스템 구축 감리용역
[발주기관] 중앙선거관리위원회
[사업금액] 110,000,000원 (부가세 포함)
[추정가격] 100,000,000원 (부가세 별도)
[납품기한] 2026년 10월 30일
[계약방법] 제한경쟁 / 총액계약 / 협상에 의한 계약
[입찰참가자격]
- 소프트웨어사업자(컴퓨터관련서비스사업, 업종코드: 1468)
- 정보시스템 감리법인(업종코드: 6146)
- 중소기업 또는 소상공인

[사업개요]
중앙선거관리위원회 선거기록관의 영구기록관리시스템을 확장 구축하는 사업에 대한
정보시스템 감리용역입니다. 기존 기록관리시스템의 기능 확장, 데이터 마이그레이션,
신규 모듈 개발에 대한 감리를 수행합니다.

[주요 과업]
1. 요구사항 분석 단계 감리 (분석 적정성, 요구사항 추적성 검증)
2. 설계 단계 감리 (아키텍처 적정성, 데이터 모델 검증)
3. 구현/테스트 단계 감리 (소스코드 품질, 테스트 충분성 검증)
4. 데이터 마이그레이션 감리 (이관 정합성, 무결성 검증)
5. 종료 단계 감리 (산출물 완전성, 인수인계 적정성)

[평가기준]
- 사업이해도 (20점): 사업 현황 분석 및 목표 설정의 적정성
- 감리수행계획 (30점): 감리 방법론, 절차, 도구의 적정성
- 감리조직 및 인력 (25점): 투입인력의 전문성 및 경험
- 품질관리방안 (15점): 감리 품질보증 체계의 적정성
- 수행실적 (10점): 유사사업 수행 실적
"""

DUMMY_COMPANY = """
[회사 프로필]
당사는 2010년 설립된 정보시스템 감리 전문법인으로, 과학기술정보통신부에 등록된
정보시스템감리법인입니다.

[주요 실적]
1. 국민건강보험공단 차세대 정보시스템 구축 감리 (2024, 2.3억원, 12개월)
   - 대규모 레거시 시스템 전환 감리, 데이터 마이그레이션 200TB 검증
   - 감리 결함 검출률 94%, 산출물 품질점수 97.2점
2. 행정안전부 전자문서관리시스템 고도화 감리 (2023, 1.5억원, 8개월)
   - 기록관리시스템 연계 감리, OAIS 표준 준수 검증
   - 일정준수율 100%, 감리조서 적합 판정률 98%
3. 대법원 사법정보시스템 클라우드 전환 감리 (2023, 1.8억원, 10개월)
   - 클라우드 마이그레이션 감리, 보안 취약점 42건 사전 검출
4. 관세청 통관시스템 재구축 감리 (2022, 2.0억원, 9개월)
5. 특허청 지식재산관리시스템 구축 감리 (2022, 1.2억원, 6개월)

[핵심 인력]
- PM: 김감리 (경력 18년, CISA/PMP/감리원, 유사사업 11건)
- 수석감리원: 이검증 (경력 14년, 정보시스템감리사, 기록관리시스템 감리 5건)
- 감리원: 박분석 (경력 10년, 정보처리기사, 데이터 마이그레이션 감리 8건)

[강점]
- 최근 5년간 공공 정보시스템 감리 23건 수행 (총 감리대가 38억원)
- 기록관리시스템 관련 감리 5건 수행 경험 (행안부, 국가기록원 등)
- 데이터 마이그레이션 전문 감리 역량 (8건, 누적 500TB 이상 검증)
- 평균 감리 결함 검출률 91.3%, 산출물 품질점수 평균 95.8점
"""

# ── V1 프롬프트 (기존 4줄) ──

V1_SYSTEM = """당신은 대한민국 공공조달 기술제안서 작성 전문가입니다.
평가위원이 높은 점수를 줄 수 있도록, 구체적이고 전문적인 제안서 섹션을 작성합니다.
모든 주장에는 근거를 제시하고, 추상적 표현을 피합니다.
마크다운 형식으로 작성하되, 제안서 특성에 맞게 표, 목록, 강조를 활용합니다."""

V1_USER = f"""## 이 회사의 과거 제안서 스타일 및 역량:
{DUMMY_COMPANY}

## 이번 공고 정보:
{DUMMY_RFP}

## 작성할 섹션: 사업이해도
평가항목: 사업 현황 분석 및 목표 설정의 적정성
배점: 20점
목표 분량: 약 4페이지
위 규칙과 컨텍스트를 반영하여 이 섹션을 작성하세요."""

# ── V2 프롬프트 ──

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rag_engine'))
from prompts.proposal_system_v2 import SYSTEM_PROMPT_V2

V2_USER = f"""## 당사의 역량 및 실적:
{DUMMY_COMPANY}

## 이번 공고 정보:
{DUMMY_RFP}

## 작성할 섹션
- **섹션명**: 사업이해도
- **평가항목**: 사업 현황 분석 및 목표 설정의 적정성
- **배점**: 20점
- **목표 분량**: 약 4페이지 (2000자 이상)

7대 원칙을 모두 적용하여 이 섹션을 작성하세요.
평가항목 '사업 현황 분석 및 목표 설정의 적정성'의 키워드가 본문에 자연스럽게 3회 이상 등장해야 합니다."""

# ── 평가 루브릭 ──

EVAL_SYSTEM = """당신은 대한민국 공공조달 기술제안서 평가위원입니다.
아래 제안서 섹션을 조달청 평가기준에 따라 냉정하고 객관적으로 평가하세요.

평가 항목별로 10점 만점 채점하고, 구체적 근거를 제시하세요:

1. 평가항목 부합도 (10점): 평가항목 키워드가 적절히 반영되었는가
2. 근거/수치 밀도 (10점): 정량적 근거, 수치, 사례가 충분한가
3. 본 사업 맞춤도 (10점): 본 사업(선거기록관 감리)에 맞춤화되어 있는가
4. 구조/가독성 (10점): 논리적 구조, 표/목록 활용, 가독성
5. 격식체 일관성 (10점): "-습니다/-입니다" 체 일관, 전문적 톤
6. 블라인드 준수 (10점): 회사명/로고/식별정보 노출 여부
7. 금지 표현 미사용 (10점): "최고 수준", "혁신적" 등 근거 없는 추상 표현
8. 차별화/전략성 (10점): 경쟁사 대비 차별화 요소가 명확한가

총점: /80
등급: 수(72+) / 우(64+) / 미(56+) / 양(48+) / 가(48미만)

반드시 항목별 점수와 감점 사유를 구체적으로 작성하세요.
마지막에 "개선 제안 3가지"를 추가하세요."""


def generate_section(system_prompt: str, user_prompt: str, label: str) -> str:
    client = OpenAI(timeout=120)
    print(f"\n{'='*60}")
    print(f"[{label}] 생성 중...")
    start = time.time()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.35,
        max_tokens=8000,
    )
    text = resp.choices[0].message.content or ""
    elapsed = time.time() - start
    tokens = resp.usage.total_tokens if resp.usage else 0

    print(f"[{label}] 완료: {len(text)}자, {elapsed:.1f}초, {tokens} 토큰")
    return text


def evaluate_section(section_text: str, label: str) -> str:
    client = OpenAI(timeout=120)
    print(f"\n[{label}] 평가 중...")

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": EVAL_SYSTEM},
            {"role": "user", "content": f"아래 제안서 '사업이해도' 섹션을 평가하세요:\n\n{section_text}"},
        ],
        temperature=0.2,
        max_tokens=3000,
    )
    return resp.choices[0].message.content or ""


def main():
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')

    # 1. V1 생성
    v1_text = generate_section(V1_SYSTEM, V1_USER, "V1 (기존 4줄 프롬프트)")

    # 2. V2 생성
    v2_text = generate_section(SYSTEM_PROMPT_V2, V2_USER, "V2 (구조화 프롬프트)")

    # 3. V1 평가
    v1_eval = evaluate_section(v1_text, "V1 평가")

    # 4. V2 평가
    v2_eval = evaluate_section(v2_text, "V2 평가")

    # 5. 결과 저장
    report = f"""# 제안서 품질 A/B 테스트 결과

## 테스트 조건
- 모델: gpt-4o-mini
- 섹션: 사업이해도 (배점 20점)
- 공고: 선거기록관 확장형 영구기록관리시스템 구축 감리용역
- 회사: 더미 감리법인 (실적 5건, 인력 3명)

---

## V1 결과 (기존 4줄 프롬프트)

### 생성된 섹션 ({len(v1_text)}자)

{v1_text}

### V1 평가

{v1_eval}

---

## V2 결과 (구조화 프롬프트)

### 생성된 섹션 ({len(v2_text)}자)

{v2_text}

### V2 평가

{v2_eval}

---

## 비교 요약

| 항목 | V1 | V2 |
|------|----|----|
| 생성 길이 | {len(v1_text)}자 | {len(v2_text)}자 |
"""
    report_path = os.path.join(output_dir, 'ab_test_result.md')
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\n{'='*60}")
    print(f"결과 저장: {report_path}")
    print(f"{'='*60}")

    # 콘솔에 평가 결과 출력
    print("\n" + "="*60)
    print("V1 평가:")
    print("="*60)
    print(v1_eval)
    print("\n" + "="*60)
    print("V2 평가:")
    print("="*60)
    print(v2_eval)


if __name__ == "__main__":
    main()
