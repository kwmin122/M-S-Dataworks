"""495 유닛 자동 분류 — LLM + 키워드 교차 검증.

Phase 1 실행 스크립트: Layer 1 document_type 필드 자동 할당
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

# rag_engine 모듈 import를 위한 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag_engine"))

import openai
from knowledge_db import KnowledgeDB
from knowledge_models import DocumentType, KnowledgeUnit, KnowledgeCategory, SourceType


# 키워드 정의
PPT_KEYWORDS = [
    "슬라이드", "발표", "pt", "청중", "프레젠테이션",
    "시각", "차트", "애니메이션", "발표자료", "스피치"
]

WBS_KEYWORDS = [
    "wbs", "일정", "간트", "공정", "m/m", "투입",
    "단계", "마일스톤", "수행계획", "공정표", "작업분류"
]

PROPOSAL_KEYWORDS = [
    "제안서", "기술제안", "사업제안", "과업", "요구사항",
    "평가", "배점", "rfp", "입찰", "기술제안서"
]

TRACK_RECORD_KEYWORDS = [
    "실적", "경력", "수행실적", "프로젝트", "유사",
    "포트폴리오", "레퍼런스", "수행이력"
]


def infer_by_keywords(unit: KnowledgeUnit) -> DocumentType:
    """키워드 기반 document_type 추론."""
    text = f"{unit.rule} {unit.explanation} {unit.subcategory}".lower()

    scores = {
        DocumentType.PPT: sum(1 for k in PPT_KEYWORDS if k in text),
        DocumentType.WBS: sum(1 for k in WBS_KEYWORDS if k in text),
        DocumentType.PROPOSAL: sum(1 for k in PROPOSAL_KEYWORDS if k in text),
        DocumentType.TRACK_RECORD: sum(1 for k in TRACK_RECORD_KEYWORDS if k in text),
    }

    max_score = max(scores.values())
    if max_score >= 2:  # 최소 2개 키워드 매칭
        return max(scores, key=scores.get)

    return DocumentType.COMMON


def classify_with_llm(unit: KnowledgeUnit, api_key: str) -> DocumentType:
    """LLM 기반 분류 (GPT-4o-mini)."""
    client = openai.OpenAI(api_key=api_key, timeout=15)

    prompt = f"""다음 공공조달 제안서 작성 지식을 분류하세요.

규칙: {unit.rule}
설명: {unit.explanation[:200] if unit.explanation else "(설명 없음)"}
카테고리: {unit.category.value}/{unit.subcategory}

분류 옵션:
- PPT: PT 발표자료 작성 전용 지식 (슬라이드, 발표, 시각화)
- WBS: 수행계획서/WBS 작성 전용 지식 (일정, 간트, 공정)
- PROPOSAL: 기술제안서 작성 전용 지식 (제안서, 평가, 과업)
- TRACK_RECORD: 실적기술서 작성 전용 지식 (실적, 경력, 수행이력)
- COMMON: 모든 문서에 공통 적용 가능한 지식

답변 형식: (PPT|WBS|PROPOSAL|TRACK_RECORD|COMMON 중 하나만 출력)
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=15,
        )
        result = resp.choices[0].message.content.strip().upper()

        # 매핑
        mapping = {
            "PPT": DocumentType.PPT,
            "WBS": DocumentType.WBS,
            "PROPOSAL": DocumentType.PROPOSAL,
            "TRACK_RECORD": DocumentType.TRACK_RECORD,
            "COMMON": DocumentType.COMMON,
        }

        return mapping.get(result, DocumentType.COMMON)
    except Exception as exc:
        print(f"  LLM 분류 실패: {exc}")
        return DocumentType.COMMON


def classify_and_validate(unit: KnowledgeUnit, api_key: str) -> DocumentType:
    """LLM + 키워드 교차 검증 — 불일치 시 COMMON."""
    llm_result = classify_with_llm(unit, api_key)
    keyword_result = infer_by_keywords(unit)

    if llm_result != keyword_result and llm_result != DocumentType.COMMON and keyword_result != DocumentType.COMMON:
        print(f"  ⚠️ 불일치: LLM={llm_result.value}, Keyword={keyword_result.value} → COMMON")
        return DocumentType.COMMON

    # LLM 우선 (COMMON이 아닌 경우)
    if llm_result != DocumentType.COMMON:
        return llm_result

    # 키워드 결과 사용
    return keyword_result


def main():
    """495 유닛 분류 실행."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # KnowledgeDB 로드 (루트 data/knowledge_db)
    kb_path = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_db")
    kb = KnowledgeDB(persist_directory=kb_path)

    total = kb.count()
    print(f"총 {total}개 유닛 분류 시작...\n")

    # 전체 유닛 로드
    all_data = kb._collection.get(include=["metadatas", "documents"])
    all_ids = all_data["ids"]
    all_metas = all_data["metadatas"]
    all_docs = all_data["documents"]

    distribution = defaultdict(int)
    disagreements = []

    for i, (unit_id, meta, doc) in enumerate(zip(all_ids, all_metas, all_docs), 1):
        # KnowledgeUnit 재구성
        unit = KnowledgeUnit(
            category=KnowledgeCategory(meta["category"]),
            subcategory=meta.get("subcategory", ""),
            rule=meta.get("rule", ""),
            explanation=doc,  # document에 전체 텍스트 저장됨
            source_type=SourceType(meta.get("source_type", "blog")),
            raw_confidence=meta.get("raw_confidence", 0.5),
            source_count=meta.get("source_count", 1),
            source_date=meta.get("source_date", ""),
            is_law_based=meta.get("is_law_based", False),
            condition=meta.get("condition", ""),
            has_conflict_flag=meta.get("has_conflict_flag", False),
        )

        # 분류
        doc_type = classify_and_validate(unit, api_key)
        distribution[doc_type] += 1

        # 메타데이터 업데이트
        meta["document_type"] = doc_type.value
        kb._collection.update(ids=[unit_id], metadatas=[meta])

        # 진행 상황 표시
        if i % 25 == 0:
            print(f"{i}/{total} 완료...")
            for dt, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
                pct = count / i * 100
                print(f"  {dt.value}: {count}개 ({pct:.1f}%)")
            print()

    print("\n=== 최종 분포 ===")
    for dt, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
        pct = count / total * 100
        print(f"{dt.value:15s}: {count:3d}개 ({pct:5.1f}%)")

    print("\n=== 예상 분포 검증 ===")
    expected = {
        DocumentType.PROPOSAL: (55, 65),
        DocumentType.COMMON: (20, 30),
        DocumentType.PPT: (5, 10),
        DocumentType.WBS: (3, 7),
        DocumentType.TRACK_RECORD: (0, 5),
    }

    all_ok = True
    for dt, (min_pct, max_pct) in expected.items():
        actual_pct = distribution[dt] / total * 100
        status = "✓" if min_pct <= actual_pct <= max_pct else "✗"
        print(f"{status} {dt.value:15s}: {actual_pct:5.1f}% (예상: {min_pct}-{max_pct}%)")
        if not (min_pct <= actual_pct <= max_pct):
            all_ok = False

    if all_ok:
        print("\n✓ 모든 분포가 예상 범위 내입니다.")
    else:
        print("\n⚠️ 일부 분포가 예상 범위를 벗어났습니다. 검토가 필요합니다.")

    print(f"\n비용 예상: 495개 × $0.0001 ≈ $0.05")


if __name__ == "__main__":
    main()
