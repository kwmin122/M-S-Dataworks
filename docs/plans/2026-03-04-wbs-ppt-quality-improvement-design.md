# WBS/PPT 품질 개선 설계 문서

**날짜:** 2026-03-04
**작성자:** Claude (이사 검증 완료)
**상태:** 승인됨 — 즉시 실행

---

## 문제 정의

### 사용자 피드백
1. **간트차트 한글 인코딩 오류** — Railway Docker 환경에서 한글 깨짐
2. **WBS/PPT 품질 심각** — 회사 차별화 없음, generic 내용만, 설득력 부족

### 근본 원인 분석

**Layer 1 (지식 DB) 문제:**
- 경로 불일치: `rag_engine/data/knowledge_db` (0개) vs `data/knowledge_db` (495개)
- 문서 타입 구분 없음: PPT/WBS도 제안서 지식만 검색
- **결과:** LLM이 아무 지식 없이 RFP만 보고 생성

**Layer 2 (회사 맞춤) 문제:**
- CompanyDB 비어있음
- profile_md 없음
- **결과:** 회사 차별화 불가

**간트차트 문제:**
- Railway Docker에 한글 폰트 미설치
- matplotlib이 fallback 폰트 사용 → 깨진 문자

---

## 해결 방향

### 우선순위 (이사 승인안)

**Phase 1: 즉시 실행 (오늘, 1-2시간)**
1. Layer 1 경로 수정
2. DocumentType 필드 추가
3. LLM + 키워드 자동 분류
4. 간트차트 폰트 설치
5. 로컬 검증

**Phase 2: 단기 실행 (1-2일)**
6. 최소 회사 온보딩 (5분 입력)
7. 템플릿 모드 (범용 초안)
8. Railway 배포

---

## 설계 상세

### 1. Layer 1 DocumentType 추가

#### 1-A. 데이터 모델

**knowledge_models.py:**
```python
class DocumentType(str, Enum):
    PPT = "ppt"              # PT 발표자료
    WBS = "wbs"              # 수행계획서/WBS
    PROPOSAL = "proposal"    # 기술제안서
    TRACK_RECORD = "track_record"  # 실적기술서
    COMMON = "common"        # 모든 문서 타입 공통

@dataclass
class KnowledgeUnit:
    # ... 기존 필드
    document_type: DocumentType = DocumentType.COMMON
```

#### 1-B. KnowledgeDB 검색 로직

**knowledge_db.py:**
```python
def search(
    self,
    query: str,
    top_k: int = 10,
    category: Optional[KnowledgeCategory] = None,
    document_types: Optional[list[DocumentType]] = None,
) -> list[KnowledgeUnit]:
    where = {}
    if category:
        where["category"] = category.value
    if document_types:
        where["document_type"] = {"$in": [dt.value for dt in document_types]}

    results = self._collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where if where else None,
    )
    # ... 기존 로직
```

#### 1-C. Orchestrator 업데이트

**모든 오케스트레이터 (ppt/wbs/proposal/track_record):**
```python
# Before
units = kb.search(query, top_k=10)

# After
units = kb.search(
    query,
    top_k=10,
    document_types=[DocumentType.PPT, DocumentType.COMMON]  # 각자 타입
)
```

---

### 2. LLM + 키워드 자동 분류

**설계 원칙:**
- LLM 문맥 이해 + 키워드 교차 검증
- 불일치 시 COMMON (안전)
- 비용: 495개 × $0.0001 = $0.05

**scripts/classify_knowledge_units.py (신규):**
```python
"""495 유닛 자동 분류 — LLM + 키워드 조합."""
import os
import openai
from knowledge_db import KnowledgeDB
from knowledge_models import DocumentType, KnowledgeUnit

PPT_KEYWORDS = ["슬라이드", "발표", "pt", "청중", "프레젠테이션", "시각", "차트"]
WBS_KEYWORDS = ["wbs", "일정", "간트", "공정", "m/m", "투입", "단계", "마일스톤"]
PROPOSAL_KEYWORDS = ["제안서", "기술제안", "과업", "요구사항", "평가", "배점", "rfp"]
TRACK_RECORD_KEYWORDS = ["실적", "경력", "수행실적", "프로젝트", "유사"]

def infer_by_keywords(unit: KnowledgeUnit) -> DocumentType:
    """키워드 기반 추론."""
    text = f"{unit.rule} {unit.explanation} {unit.subcategory}".lower()

    scores = {
        DocumentType.PPT: sum(1 for k in PPT_KEYWORDS if k in text),
        DocumentType.WBS: sum(1 for k in WBS_KEYWORDS if k in text),
        DocumentType.PROPOSAL: sum(1 for k in PROPOSAL_KEYWORDS if k in text),
        DocumentType.TRACK_RECORD: sum(1 for k in TRACK_RECORD_KEYWORDS if k in text),
    }

    max_score = max(scores.values())
    if max_score >= 2:
        return max(scores, key=scores.get)
    return DocumentType.COMMON

def classify_with_llm(unit: KnowledgeUnit, api_key: str) -> DocumentType:
    """LLM 기반 분류."""
    client = openai.OpenAI(api_key=api_key, timeout=10)

    prompt = f"""다음 공공조달 제안서 작성 지식을 분류하세요.

규칙: {unit.rule}
설명: {unit.explanation[:200]}

분류 옵션:
- PPT: PT 발표자료 작성 전용 지식
- WBS: 수행계획서/WBS 작성 전용 지식
- PROPOSAL: 기술제안서 작성 전용 지식
- COMMON: 모든 문서에 공통 적용 가능한 지식

답변: (PPT|WBS|PROPOSAL|COMMON만 출력)
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        result = resp.choices[0].message.content.strip().upper()
        return DocumentType(result.lower())
    except Exception as exc:
        print(f"LLM 분류 실패: {exc}")
        return DocumentType.COMMON

def classify_and_validate(unit: KnowledgeUnit, api_key: str) -> DocumentType:
    """LLM + 키워드 교차 검증."""
    llm_result = classify_with_llm(unit, api_key)
    keyword_result = infer_by_keywords(unit)

    if llm_result != keyword_result:
        print(f"⚠️ 불일치: LLM={llm_result.value}, Keyword={keyword_result.value} → COMMON")
        return DocumentType.COMMON

    return llm_result

def main():
    """495 유닛 분류 실행."""
    api_key = os.environ.get("OPENAI_API_KEY")
    kb = KnowledgeDB(persist_directory="../data/knowledge_db")

    # 전체 유닛 로드
    all_ids = kb._collection.get()["ids"]
    print(f"총 {len(all_ids)}개 유닛 분류 시작...")

    distribution = {dt: 0 for dt in DocumentType}

    for i, unit_id in enumerate(all_ids, 1):
        # ChromaDB에서 유닛 로드
        result = kb._collection.get(ids=[unit_id], include=["metadatas"])
        meta = result["metadatas"][0]

        unit = KnowledgeUnit(
            category=meta["category"],
            subcategory=meta.get("subcategory", ""),
            rule=meta.get("rule", ""),
            explanation="",  # 임베딩에만 있음
            # ... 기타 필드
        )

        # 분류
        doc_type = classify_and_validate(unit, api_key)
        distribution[doc_type] += 1

        # 메타데이터 업데이트
        meta["document_type"] = doc_type.value
        kb._collection.update(ids=[unit_id], metadatas=[meta])

        if i % 50 == 0:
            print(f"{i}/{len(all_ids)} 완료... {distribution}")

    print("\n=== 최종 분포 ===")
    for dt, count in distribution.items():
        pct = count / len(all_ids) * 100
        print(f"{dt.value}: {count}개 ({pct:.1f}%)")

if __name__ == "__main__":
    main()
```

---

### 3. 간트차트 한글 폰트

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

# 한글 폰트 설치 (NanumGothic, Noto CJK)
RUN apt-get update && apt-get install -y \
    fonts-nanum \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# matplotlib 폰트 캐시 재생성
RUN python -c "import matplotlib.pyplot as plt; plt.figure()"

# ... 나머지 기존 Dockerfile
```

**검증:**
- wbs_generator.py의 `_find_korean_font()` 수정 불필요
- `/usr/share/fonts/truetype/nanum/` 자동 감지

---

### 4. 최소 회사 온보딩 (5분)

#### 4-A. 접점 단순화

**유지:**
- A: 문서 생성 클릭 시 (CompanyDB 체크 → 선택 다이얼로그)
- D: 설정 페이지 "회사 DB 구축"

**제거:**
- B: RFP 분석 후 배너 (너무 이른 시점)

#### 4-B. 최소 입력 항목

```
Step 1 (필수):
  회사명: [          ]
  대표 실적 1개:
    - 프로젝트명: [          ]
    - 발주처: [          ]
    - 기간: [YYYY-MM] ~ [YYYY-MM]

Step 2 (필수):
  핵심 인력 1명:
    - 이름: [          ]
    - 역할: [PM/PL/개발자/...]
    - 경력: [  ]년

Step 3 (선택):
  과거 제안서 업로드 (문체 학습용)
  [파일 선택]

[완료] ← 즉시 맞춤 제안서 생성 가능
```

**예상 소요 시간:** 5분
**즉시 가치:** 실적 1개 + 인력 1명만으로 맞춤화 체감 가능

---

### 5. 템플릿 모드 (범용 초안)

**AS-IS (거부):** 가이드만 제공 (빈 문서)
**TO-BE (승인):** Layer 1으로 범용 초안 생성 + 회사 맞춤 부분 강조

**출력 예시:**
```markdown
# 1. 사업 이해

본 사업은 KOICA 봉사단 교육체계의 디지털 전환을 목표로 합니다.
기존 오프라인 중심 교육의 접근성 한계를 극복하고,
비대면 환경에서도 효과적인 교육을 제공하기 위한 플랫폼 구축이 핵심입니다.

⚠️ **회사 맞춤 수정 필요:**
- [ ] 우리 회사의 교육 플랫폼 구축 실적 추가
- [ ] 우리 회사의 디지털 전환 전문성 강조
- [ ] 우리만의 차별화된 접근법 서술

💡 **작성 팁 (공공조달 지식):**
• 발주기관 관점에서 문제를 서술하세요
• 정량적 목표를 명확히 하세요 (예: "교육 접근성 30% 향상")
• 부록의 기술 명세서를 참고하세요
```

**구현:**
- proposal_orchestrator.py에 `template_mode=True` 파라미터 추가
- section_writer에서 company_context 없으면 체크박스 추가
- Layer 1 지식은 "작성 팁"으로 제공

---

### 6. 검증 계획

#### 6-A. 분류 정확도 (자동)

```python
# 분포 확인
expected = {
    DocumentType.PROPOSAL: (55, 65),  # 55-65%
    DocumentType.COMMON: (20, 30),
    DocumentType.PPT: (5, 10),
    DocumentType.WBS: (3, 7),
}

for dt, (min_pct, max_pct) in expected.items():
    actual_pct = distribution[dt] / 495 * 100
    assert min_pct <= actual_pct <= max_pct, f"{dt} 비율 이상: {actual_pct}%"
```

#### 6-B. 실제 생성 품질 (Before/After)

```python
# 동일 RFP로 비교
test_rfp = load_test_rfp("KOICA 디지털 전환")

# Before: document_type 없이
ppt_before = generate_ppt(test_rfp, use_document_type_filter=False)

# After: document_type 필터
ppt_after = generate_ppt(test_rfp, use_document_type_filter=True)

# 지식 비교
print("Before 지식:", [u.rule[:50] for u in ppt_before.knowledge[:3]])
print("After 지식:", [u.rule[:50] for u in ppt_after.knowledge[:3]])
# 기대: After는 "슬라이드", "발표" 관련 지식만
```

#### 6-C. 사용자 테스트 (실제 공고 3개)

1. KOICA 디지털 전환 RFP → PPT 생성
2. 교육청 시스템 구축 RFP → WBS 생성
3. 행정안전부 플랫폼 RFP → 제안서 생성

→ 사용자 직접 확인: "품질 개선되었나?"

---

### 7. 배포 전략

#### Phase 0: 로컬 테스트 (1일)

```bash
# 1. Layer 1 경로 수정
cd rag_engine
sed -i 's|"./data/knowledge_db"|"../data/knowledge_db"|g' main.py ppt_orchestrator.py wbs_orchestrator.py

# 검증
python -c "from knowledge_db import KnowledgeDB; kb=KnowledgeDB(); print(kb.count())"
# 기대: 495

# 2. document_type 추가 (코드 수정)
# knowledge_models.py, knowledge_db.py 수정

# 3. 자동 분류 실행
cd ../scripts
python classify_knowledge_units.py
# 기대: 분포 정상, LLM-키워드 일치율 95%+

# 4. 실제 품질 비교
python tests/test_quality_before_after.py
# 기대: PPT/WBS에 전용 지식만

# 5. 간트차트 폰트 (Docker)
docker build -t kirabot-test .
docker run kirabot-test python -c "from wbs_generator import _find_korean_font; print(_find_korean_font())"
# 기대: /usr/share/fonts/truetype/nanum/NanumGothic.ttf
```

#### Phase 1: Railway 배포

```bash
# 백업
railway run "cd data && tar -czf knowledge_db_backup.tar.gz knowledge_db/"

# 배포
git add -A
git commit -m "fix: Layer 1 document_type + 간트차트 폰트 + 회사 온보딩"
git push railway main

# 즉시 검증
curl https://kirabot.up.railway.app/warmup
# 기대: {"status": "warmed_up", "message": "ChromaDB initialized"}

curl https://kirabot.up.railway.app/api/company/status
# 기대: {"has_data": false, ...}
```

#### 롤백 트리거

- Layer 1 로드 실패 (count != 495)
- 문서 생성 에러율 > 10%
- 사용자 "품질 더 떨어짐" 피드백

```bash
# 롤백
git revert HEAD
git push railway main --force
```

---

## 성공 지표

| 지표 | Before | Target | 측정 |
|------|--------|--------|------|
| Layer 1 지식 활용 | 0개 | 495개 | kb.count() |
| PPT 전용 지식 비율 | 0% | 100% | 검색 필터 정확도 |
| 문서 생성 성공률 | 100% | 100% | 에러율 유지 |
| 사용자 재생성 요청 | ? | -30% | 로그 분석 |
| 회사 정보 입력율 | 0% | 30%+ | DB 체크 |

---

## 구현 순서 (체크리스트)

**Phase 1: 즉시 (오늘)**
- [ ] knowledge_models.py: DocumentType enum 추가
- [ ] KnowledgeUnit: document_type 필드 추가
- [ ] knowledge_db.py: search() document_types 파라미터
- [ ] scripts/classify_knowledge_units.py 작성
- [ ] 495 유닛 자동 분류 실행
- [ ] 분포 검증 (자동)
- [ ] ppt/wbs/proposal/track_record orchestrator 업데이트
- [ ] 실제 생성 품질 비교 (Before/After)
- [ ] Dockerfile 한글 폰트 추가
- [ ] Docker 빌드 + 폰트 검증
- [ ] Git commit

**Phase 2: 단기 (1-2일)**
- [ ] 최소 회사 온보딩 UI (5분 입력)
- [ ] template_mode 구현 (범용 초안)
- [ ] 사용자 테스트 (실제 공고 3개)
- [ ] Railway 배포 (단계적)
- [ ] 모니터링 + 롤백 준비

---

## 거부된 항목

- ❌ RFP 분석 후 배너 (접점 B) — 사용자 피로
- ❌ 복잡한 회사 정보 입력 — 이탈 위험
- ❌ 가이드만 제공하는 템플릿 — 가치 낮음
- ❌ 수동 검증 주관적 기준 — 자동화 + 실제 품질
- ❌ 즉시 배포 — 단계적 + 롤백

---

**이사 최종 승인: 2026-03-04**
**실행 책임자: Claude**
**예상 완료: Phase 1 (오늘), Phase 2 (2일 이내)**
