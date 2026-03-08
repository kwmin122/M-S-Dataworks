# Kira Bot 전체 플로우 테스트 시나리오

**생성일:** 2026-03-08
**목적:** 더미 데이터 기반 E2E 플로우 검증

---

## 시나리오 매트릭스

| ID | 회사 유형 | 공고 유형 | 예상 결과 | 검증 포인트 |
|----|----------|----------|----------|-----------|
| TS-001 | 대기업 IT (삼성SDS) | 공공 클라우드 | GO (95점) | 매출/인력 충족, 실적 풍부 |
| TS-002 | 중소 제조 A | 공공 클라우드 | NO-GO (45점) | 업종 불일치, 실적 부족 |
| TS-003 | IT 중견 (더존비즈온) | 금융 ERP | GO (88점) | ERP 전문성, 금융 실적 |
| TS-004 | 중소 컨설팅 A | 정보화전략 | GO (82점) | 컨설팅 실적, 소규모 매출 OK |
| TS-005 | 중견 건설 (현대건설) | 공공 클라우드 | NO-GO (50점) | 업종 불일치 (건설↔IT) |
| TS-006 | 보안전문 A | 보안관제 | GO (92점) | 보안 자격증, 실적 일치 |
| TS-007 | 시스템통합 A | 네트워크 인프라 | GO (90점) | 인프라 전문성 |
| TS-008 | 연구기업 A | AI 연구용역 | GO (85점) | R&D 실적, 박사급 인력 |
| TS-009 | 솔루션기업 B | 빅데이터 플랫폼 | GO (87점) | 빅데이터 실적, 기술스택 일치 |
| TS-010 | IT서비스 C | MSP 운영 | GO (89점) | MSP 실적, 운영 인력 |

---

## 시나리오 상세

### TS-001: 대기업 IT × 공공 클라우드 (HIGH MATCH)

**입력:**
- 회사: 삼성SDS (company_001)
- 공고: `입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf`

**Step 1: 공고 업로드**
```bash
curl -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts001
```
- 예상: 200 OK, `{"status": "success", "chunks": 13}`

**Step 2: 회사 문서 업로드**
```bash
curl -F "file=@data/company_docs/삼성SDS_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts001
```
- 예상: 200 OK, `{"status": "success", "chunks": 10}`

**Step 3: RFP 분석**
```bash
curl -X POST http://localhost:8000/api/analyze?session_id=ts001
```
- 예상 자격요건:
  - 매출: 최근 3년 평균 100억 이상
  - 유사 실적: 공공데이터 or 클라우드 실적 3건 이상
  - 기술인력: 정보처리기사 5명 이상

**Step 4: GO/NO-GO 매칭**
- 예상 점수: 95/100
  - 매출 충족: ✅ (15조 >> 100억)
  - 유사 실적: ✅ (클라우드 실적 8건)
  - 기술인력: ✅ (정보처리기사 1,200명)
- 최종 판단: "GO"

**Step 5: 제안서 생성 (v2)**
```bash
curl -X POST http://localhost:8001/api/generate-proposal-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "company_001",
    "rfp_text": "...",
    "total_pages": 80
  }'
```
- 예상: 80페이지 DOCX 생성
- 검증:
  - 블라인드 체크 통과 (회사명 0건)
  - 모호 표현 < 5건
  - Layer 1 지식 주입 확인

**Step 6: WBS 생성**
```bash
curl -X POST http://localhost:8001/api/generate-wbs \
  -H "Content-Type: application/json" \
  -d '{"company_id": "company_001", "rfp_text": "..."}'
```
- 예상: XLSX (간트차트) + DOCX 수행계획서
- 검증: 태스크 20~30개, 마일스톤 4~5개

**Step 7: PPT 생성**
```bash
curl -X POST http://localhost:8001/api/generate-ppt \
  -H "Content-Type: application/json" \
  -d '{"company_id": "company_001", "proposal_path": "..."}'
```
- 예상: 25~30 슬라이드 PPTX, 예상질문 10개
- 검증: KRDS 디자인 토큰, 6종 슬라이드 타입

**Step 8: 실적기술서 생성**
```bash
curl -X POST http://localhost:8001/api/generate-track-record \
  -H "Content-Type: application/json" \
  -d '{"company_id": "company_001", "requirements": {...}}'
```
- 예상: DOCX, 매칭 실적 5건 + 인력 3명
- 검증: CompanyDB 실적 정확히 매칭

**Step 9: 체크리스트 확인**
```bash
curl -X POST http://localhost:8001/api/checklist \
  -H "Content-Type: application/json" \
  -d '{"rfp_text": "..."}'
```
- 예상: 15~20개 항목 (제출서류, 자격증명)

**Step 10: 수정 학습**
- 사용자 수정 3회 시뮬레이션
- 예상: Layer 2 자동 학습 트리거

---

### TS-002: 중소 제조 × 공공 클라우드 (LOW MATCH)

**입력:**
- 회사: 제조기업 A (company_007)
- 공고: 동일 (공공데이터 컨설팅)

**예상 결과:**
- GO/NO-GO: NO-GO (45점)
- 매출 충족: ✅ (100억)
- 유사 실적: ❌ (제조/방산만 있음, 클라우드 0건)
- 기술인력: ⚠️ (정보처리기사 2명, 부족)

**검증 포인트:**
- matcher가 "업종 불일치" 정확히 감지
- 제안서 생성 안 함 (NO-GO 시 차단)

**Step-by-step 절차:**
```bash
# Step 1: 공고 업로드
curl -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts002

# Step 2: 회사 문서 업로드
curl -F "file=@data/company_docs/제조기업A_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts002

# Step 3: 분석 실행
curl -X POST http://localhost:8000/api/analyze?session_id=ts002
```

---

### TS-003: IT 중견 × 금융 ERP (MODERATE-HIGH MATCH)

**입력:**
- 회사: 더존비즈온 (company_011)
- 공고: 금융권 ERP 구축

**예상 결과:**
- GO/NO-GO: GO (88점)
- ERP 전문성: ✅
- 금융권 실적: ✅ (5건)
- 기술인력: ✅

**검증 포인트:**
- ERP 도메인 전문성 매칭
- 금융권 실적 우선 순위 정렬

**Step-by-step 절차:**
```bash
# Step 1-3: 업로드 + 분석
curl -F "file=@docs/test/입찰공고문_금융ERP.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts003

curl -F "file=@data/company_docs/더존비즈온_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts003

curl -X POST http://localhost:8000/api/analyze?session_id=ts003
```

---

### TS-004: 중소 컨설팅 × 정보화전략 (MODERATE MATCH)

**입력:**
- 회사: 컨설팅기업 A (company_005)
- 공고: 정보화전략 수립

**예상 결과:**
- GO/NO-GO: GO (82점)
- 컨설팅 실적: ✅ (8건)
- 소규모 매출: ✅ (50억, 기준 30억)
- 전문 인력: ✅ (PMP 15명)

**검증 포인트:**
- 소규모 회사도 전문성 있으면 GO
- 컨설팅 카테고리 매칭 정확도

**Step-by-step 절차:**
```bash
curl -F "file=@docs/test/입찰공고문_정보화전략.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts004

curl -F "file=@data/company_docs/컨설팅기업A_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts004

curl -X POST http://localhost:8000/api/analyze?session_id=ts004
```

---

### TS-005: 중견 건설 × 공공 클라우드 (DOMAIN MISMATCH)

**입력:**
- 회사: 현대건설 (company_003)
- 공고: 공공데이터 컨설팅

**예상 결과:**
- GO/NO-GO: NO-GO (50점)
- 매출 충족: ✅ (5조, 충분)
- 업종 불일치: ❌ (건설 ↔ IT)
- 기술인력: ❌ (건축사 위주, IT 자격증 부족)

**검증 포인트:**
- 대기업이라도 업종 불일치 시 NO-GO
- 매출만으로 GO 판단하지 않음

**Step-by-step 절차:**
```bash
curl -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts005

curl -F "file=@data/company_docs/현대건설_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts005

curl -X POST http://localhost:8000/api/analyze?session_id=ts005
```

---

### TS-006: 보안전문 × 보안관제 (PERFECT MATCH)

**입력:**
- 회사: 보안기업 A (company_017)
- 공고: 보안관제센터 구축

**예상 결과:**
- GO/NO-GO: GO (92점)
- 보안 자격증: ✅ (정보보안기사 50명)
- 보안 실적: ✅ (10건)
- 전문성: ✅ (보안관제 특화)

**검증 포인트:**
- 도메인 완벽 일치 시 높은 점수
- 보안 자격증 가중치 반영

**Step-by-step 절차:**
```bash
curl -F "file=@docs/test/입찰공고문_보안관제.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts006

curl -F "file=@data/company_docs/보안기업A_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts006

curl -X POST http://localhost:8000/api/analyze?session_id=ts006
```

---

### TS-007: 시스템통합 × 네트워크 인프라 (HIGH MATCH)

**입력:**
- 회사: 시스템통합기업 A (company_015)
- 공고: 네트워크 인프라 고도화

**예상 결과:**
- GO/NO-GO: GO (90점)
- 인프라 실적: ✅ (7건)
- 네트워크 전문성: ✅
- 기술인력: ✅ (네트워크 엔지니어 30명)

**검증 포인트:**
- SI 카테고리 세부 매칭
- 인프라 vs 애플리케이션 구분

**Step-by-step 절차:**
```bash
curl -F "file=@docs/test/입찰공고문_네트워크인프라.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts007

curl -F "file=@data/company_docs/시스템통합기업A_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts007

curl -X POST http://localhost:8000/api/analyze?session_id=ts007
```

---

### TS-008: 연구기업 × AI 연구용역 (RESEARCH MATCH)

**입력:**
- 회사: 연구기업 A (company_009)
- 공고: AI 기반 데이터 분석 연구

**예상 결과:**
- GO/NO-GO: GO (85점)
- R&D 실적: ✅ (12건)
- 박사급 인력: ✅ (5명)
- AI 전문성: ✅

**검증 포인트:**
- 연구용역 카테고리 매칭
- 학력 요건 (박사급) 반영

**Step-by-step 절차:**
```bash
curl -F "file=@docs/test/입찰공고문_AI연구.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts008

curl -F "file=@data/company_docs/연구기업A_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts008

curl -X POST http://localhost:8000/api/analyze?session_id=ts008
```

---

### TS-009: 솔루션기업 × 빅데이터 플랫폼 (TECH MATCH)

**입력:**
- 회사: 솔루션기업 B (company_014)
- 공고: 빅데이터 플랫폼 구축

**예상 결과:**
- GO/NO-GO: GO (87점)
- 빅데이터 실적: ✅ (6건)
- 기술스택 일치: ✅ (Hadoop, Spark)
- 자체 솔루션 보유: ✅

**검증 포인트:**
- 기술스택 키워드 매칭
- 자체 솔루션 가점 반영

**Step-by-step 절차:**
```bash
curl -F "file=@docs/test/입찰공고문_빅데이터.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts009

curl -F "file=@data/company_docs/솔루션기업B_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts009

curl -X POST http://localhost:8000/api/analyze?session_id=ts009
```

---

### TS-010: IT서비스 × MSP 운영 (OPERATION MATCH)

**입력:**
- 회사: IT서비스기업 C (company_020)
- 공고: 클라우드 MSP 운영

**예상 결과:**
- GO/NO-GO: GO (89점)
- MSP 실적: ✅ (8건)
- 운영 인력: ✅ (24시간 운영조 편성 가능)
- 클라우드 자격증: ✅ (AWS/Azure 인증 40명)

**검증 포인트:**
- 운영 vs 구축 카테고리 구분
- 24시간 운영 조건 충족

**Step-by-step 절차:**
```bash
curl -F "file=@docs/test/입찰공고문_MSP.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts010

curl -F "file=@data/company_docs/IT서비스기업C_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts010

curl -X POST http://localhost:8000/api/analyze?session_id=ts010
```

---

## 자동화 스크립트

```bash
#!/bin/bash
# scripts/run_all_scenarios.sh

BASE_URL="http://localhost:8000"

declare -A scenarios=(
  ["ts001"]="삼성SDS_회사소개서.pdf|입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf"
  ["ts002"]="제조기업A_회사소개서.pdf|입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf"
  ["ts003"]="더존비즈온_회사소개서.pdf|입찰공고문_금융ERP.pdf"
  ["ts004"]="컨설팅기업A_회사소개서.pdf|입찰공고문_정보화전략.pdf"
  ["ts005"]="현대건설_회사소개서.pdf|입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf"
  ["ts006"]="보안기업A_회사소개서.pdf|입찰공고문_보안관제.pdf"
  ["ts007"]="시스템통합기업A_회사소개서.pdf|입찰공고문_네트워크인프라.pdf"
  ["ts008"]="연구기업A_회사소개서.pdf|입찰공고문_AI연구.pdf"
  ["ts009"]="솔루션기업B_회사소개서.pdf|입찰공고문_빅데이터.pdf"
  ["ts010"]="IT서비스기업C_회사소개서.pdf|입찰공고문_MSP.pdf"
)

for scenario_id in "${!scenarios[@]}"; do
  IFS='|' read -r company_file bid_file <<< "${scenarios[$scenario_id]}"

  echo "=========================================="
  echo "Running $scenario_id..."
  echo "=========================================="

  # Step 1: 공고 업로드
  curl -s -F "file=@docs/test/$bid_file" \
    "$BASE_URL/api/upload_target?session_id=$scenario_id" | jq .

  # Step 2: 회사 문서 업로드
  curl -s -F "file=@data/company_docs/$company_file" \
    "$BASE_URL/api/upload_company?session_id=$scenario_id" | jq .

  # Step 3: 분석 실행
  curl -s -X POST "$BASE_URL/api/analyze?session_id=$scenario_id" | jq .

  echo "✅ $scenario_id completed"
  echo ""
done
```

---

## 검증 체크리스트

각 시나리오 실행 후 다음 항목 확인:

**기본 동작:**
- [ ] 공고 업로드 성공 (200 OK)
- [ ] 회사 문서 업로드 성공 (200 OK)
- [ ] RFP 분석 완료 (자격요건 추출)
- [ ] GO/NO-GO 점수 생성

**매칭 정확도:**
- [ ] HIGH MATCH 시나리오: 85점 이상
- [ ] LOW MATCH 시나리오: 50점 이하
- [ ] DOMAIN MISMATCH: 업종 불일치 감지

**문서 생성:**
- [ ] 제안서 DOCX 생성 (블라인드 체크 통과)
- [ ] WBS XLSX/DOCX 생성
- [ ] PPT PPTX 생성 (KRDS 디자인)
- [ ] 실적기술서 DOCX 생성

**학습 루프:**
- [ ] 수정 diff 추출
- [ ] Layer 2 자동 학습 트리거

---

## 예상 결과 요약

| 시나리오 | 예상 점수 | 예상 판단 | 핵심 검증 사항 |
|---------|-----------|-----------|---------------|
| TS-001 | 95 | GO | 대기업 IT × 클라우드 완벽 매칭 |
| TS-002 | 45 | NO-GO | 제조 × IT 업종 불일치 |
| TS-003 | 88 | GO | ERP 전문성 매칭 |
| TS-004 | 82 | GO | 소규모 전문 컨설팅 인정 |
| TS-005 | 50 | NO-GO | 대기업이라도 업종 불일치 |
| TS-006 | 92 | GO | 보안 도메인 완벽 일치 |
| TS-007 | 90 | GO | 인프라 전문성 매칭 |
| TS-008 | 85 | GO | 연구용역 매칭 |
| TS-009 | 87 | GO | 기술스택 매칭 |
| TS-010 | 89 | GO | 운영 vs 구축 구분 |
