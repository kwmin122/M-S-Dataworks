# 더미 데이터 생성 설계

**작성일:** 2026-03-08
**목적:** Kira Bot 전체 플로우 E2E 검증용 현실적 더미 데이터 생성

---

## 배경

**요구사항:**
- 공고 검색 → RFP 분석 → GO/NO-GO → 제안서/WBS/PPT/실적 생성까지 전체 파이프라인 검증
- 현실적인 회사 데이터 20개 (다양한 산업/규모)
- 실행 가능한 테스트 시나리오 문서

**현재 상태:**
- `docs/test/`: 공고 13개 존재
- `docs/dummy/`: 회사소개서 1개 (넥스트웨이브)
- CompanyDB: 비어있음

**목표:**
- 회사 20개 (회사소개서 PDF + CompanyDB 실적/인력)
- 테스트 시나리오 10~15개 (HIGH/LOW/MEDIUM MATCH)
- 실제 실행 가능한 검증 플로우

---

## 설계

### 1. 회사 20개 선정

**A그룹 10개 (다양한 산업/규모):**

| # | 회사명 | 매출 | 인원 | 산업 | 비고 |
|---|-------|------|------|------|------|
| 1 | 삼성SDS | 15조 | 25,000명 | 대기업 IT | 클라우드/AI/DX |
| 2 | LG CNS | 5조 | 8,000명 | 대기업 IT | 스마트시티/공공SI |
| 3 | 현대건설 | 20조 | 6,000명 | 중견 건설 | 토목/건축/플랜트 |
| 4 | 대우건설 | 8조 | 3,500명 | 중견 건설 | 주택/인프라 |
| 5 | 컨설팅사 A | 50억 | 30명 | 중소 컨설팅 | 정보화전략/DX |
| 6 | 컨설팅사 B | 80억 | 50명 | 중소 컨설팅 | 공공행정개선 |
| 7 | 제조기업 A | 100억 | 80명 | 중소 제조 | 방산부품/정밀기계 |
| 8 | 제조기업 B | 150억 | 120명 | 중소 제조 | 신재생에너지/ESS |
| 9 | 연구기업 A | 40억 | 25명 | 중소 R&D | AI/빅데이터 연구 |
| 10 | 연구기업 B | 60억 | 35명 | 중소 R&D | 바이오/헬스케어 |

**B그룹 10개 (IT 중견, 500억~1,500억급):**

| # | 회사명 | 매출 | 인원 | 주요 사업 |
|---|-------|------|------|-----------|
| 11 | 더존비즈온 | 4,500억 | 1,800명 | ERP/그룹웨어 |
| 12 | 한국전산원 협력사 | 800억 | 300명 | 통신SW/보안 |
| 13 | 가비아 | 1,200억 | 500명 | 클라우드/호스팅 |
| 14 | 솔루션기업 A | 600억 | 250명 | 공공SI/금융IT |
| 15 | 솔루션기업 B | 500억 | 200명 | 빅데이터/AI플랫폼 |
| 16 | 시스템통합 A | 700억 | 280명 | 네트워크/인프라 |
| 17 | 시스템통합 B | 550억 | 220명 | 클라우드마이그레이션 |
| 18 | 보안전문 A | 400억 | 150명 | 정보보안/컴플라이언스 |
| 19 | 보안전문 B | 450억 | 180명 | 보안관제/침해대응 |
| 20 | IT서비스 C | 520억 | 190명 | MSP/DevOps/인프라운영 |

**선정 기준:**
- 나라장터 공개 입찰 이력 기반 (2023-2025)
- 공공조달 실적 상위권 기업
- 다양한 산업/규모 분포

---

### 2. 회사소개서 구조 (넥스트웨이브 템플릿)

**10페이지 구성:**

1. **표지** — 회사명 (국문/영문), 슬로건, COMPANY PROFILE 2025
2. **회사 개요** — 설립일, 매출, 임직원, 기술인력 비율, 주요 사업 영역 (4개 테이블), 본사 정보
3. **회사 연혁** — 설립~최근 주요 이벤트 (연도별), 인증/매출/프로젝트 성장
4. **조직 및 인력** — 조직도, 부서별 인원, 기술 자격증 현황
5-7. **주요 사업 실적** — 최근 3개년 프로젝트 10~15건 (프로젝트명, 발주처, 기간, 금액, 역할)
8. **기술 역량** — 보유 기술 스택, 특허/인증/수상, R&D 투자
9. **주요 고객사** — 공공기관, 민간 기업 목록
10. **비전/강점** — 미션/비전/핵심가치, 경쟁 우위, 연락처

**데이터 생성 방식:**
- **실제 정보 (접근 A):** 회사명, 매출, 설립일, 주요 사업영역, 조직 구조
- **합성 정보 (접근 C):** 대표자명, 법인번호, 구체적 프로젝트 세부사항, 직원 개인 정보

---

### 3. CompanyDB 데이터 구조

**company_profile (회사 기본 정보):**
```json
{
  "company_id": "company_001",
  "company_name": "삼성SDS",
  "established": "1985-03",
  "revenue": 15000000000000,
  "employees": 25000,
  "tech_employees": 18000,
  "business_areas": ["클라우드", "AI/빅데이터", "DX컨설팅", "보안"]
}
```

**track_records (프로젝트 실적):**
```json
{
  "record_id": "rec_001_001",
  "company_id": "company_001",
  "project_name": "행정안전부 클라우드 전환 사업",
  "client": "행정안전부",
  "period": "2023.03 ~ 2024.12",
  "amount": 15000000000,
  "role": "주관사",
  "description": "온프레미스 → AWS 클라우드 전환, 300+ 시스템 마이그레이션",
  "tech_stack": ["AWS", "Kubernetes", "Terraform", "MSA"],
  "category": "클라우드"
}
```

**personnel (인력 정보):**
```json
{
  "personnel_id": "per_001_001",
  "company_id": "company_001",
  "name": "김철수",
  "position": "수석컨설턴트",
  "career_years": 12,
  "education": "서울대 컴퓨터공학 석사",
  "certifications": ["PMP", "AWS SAP", "정보처리기사"],
  "major_projects": ["행정안전부 클라우드 전환", "국방부 DX 컨설팅"],
  "expertise": ["클라우드 아키텍처", "DevOps", "보안"]
}
```

**ChromaDB 저장:**
- Collection: `company_track_records`, `company_personnel`
- ID: `{company_id}_{sha256(프로젝트명:역할:기간)[:12]}`
- Metadata: company_id, category, amount, period, tech_stack
- Document: 프로젝트 설명 전문 (임베딩용)

**데이터 규모:**
- 실적: 회사 20개 × 평균 12건 = 240건
- 인력: 회사 20개 × 평균 8명 = 160명

---

### 4. 테스트 시나리오 문서

**파일:** `docs/test/TEST_SCENARIOS.md`

**시나리오 매트릭스:**

| ID | 회사 유형 | 공고 유형 | 예상 결과 | 검증 포인트 |
|----|----------|----------|----------|-----------|
| TS-001 | 대기업 IT (삼성SDS) | 공공 클라우드 | GO (95점) | 매출/인력 충족, 실적 풍부 |
| TS-002 | 중소 제조 A | 공공 클라우드 | NO-GO (45점) | 업종 불일치, 실적 부족 |
| TS-003 | IT 중견 (더존) | 금융 ERP | GO (88점) | ERP 전문성, 금융 실적 |

**시나리오 상세 (예: TS-001):**

**입력:**
- 회사: 삼성SDS (company_001)
- 공고: `입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf`

**플로우:**
1. **공고 업로드** → PDF 파싱 성공, 13페이지 추출
2. **RFP 분석** → 매출 100억+, 유사 실적 3건+, 기술인력 5명+ 추출
3. **회사 문서 업로드** → 10페이지 파싱, CompanyDB 저장 (실적 12건, 인력 8명)
4. **GO/NO-GO 매칭** → 95/100점, "GO" 판단
5. **제안서 생성 (v2)** → 80페이지 DOCX, 블라인드 체크 통과
6. **WBS 생성** → XLSX (간트차트) + DOCX
7. **PPT 생성** → 25슬라이드 PPTX, 예상질문 10개
8. **실적기술서 생성** → DOCX, 매칭 실적 5건
9. **체크리스트** → 15~20개 항목 추출
10. **수정 학습** → 3회 수정 후 Layer 2 자동 학습

**검증 포인트:**
- GO/NO-GO 점수 90점 이상
- 매출/실적/인력 모두 충족
- 제안서 블라인드 위반 0건
- KRDS 디자인 토큰 적용 확인

**시나리오 커버리지:**
- HIGH MATCH (GO): 5개
- LOW MATCH (NO-GO): 3개
- MEDIUM MATCH (조건부): 3개
- EDGE CASE (컨소시엄, 예외): 2개

---

### 5. 생성 스크립트

**구조:**
```
scripts/
├── generate_dummy_data.py          # 메인 오케스트레이터
├── dummy_data/
│   ├── company_generator.py        # 회사소개서 PDF 생성 (reportlab)
│   ├── company_data_builder.py     # CompanyDB 적재
│   ├── company_profiles.json       # 회사 20개 기본 정보 (수동 큐레이션)
│   ├── project_templates.json      # 프로젝트 실적 템플릿
│   └── personnel_generator.py      # 인력 정보 합성 (Faker)
```

**company_profiles.json (수동 큐레이션):**
```json
{
  "company_001": {
    "name": "삼성SDS",
    "name_en": "Samsung SDS",
    "established": "1985-03",
    "revenue": 15000000000000,
    "employees": 25000,
    "tech_ratio": 0.72,
    "business_areas": ["클라우드", "AI/빅데이터", "DX컨설팅", "보안"],
    "certifications": {
      "정보처리기사": 1200,
      "PMP": 450,
      "AWS_SAA": 380
    },
    "major_clients": ["행정안전부", "국방부", "금융위원회"],
    "real_benchmark": true,
    "sensitive_info": "synthetic"
  }
}
```

**실행 방법:**
```bash
# 1. 회사 프로필 수동 큐레이션 (1~2시간)
vi scripts/dummy_data/company_profiles.json

# 2. 의존성 설치
pip install reportlab Faker

# 3. 스크립트 실행
python scripts/generate_dummy_data.py

# 4. 검증
ls data/company_docs/          # 20개 PDF
cd rag_engine && python -c "from company_db import CompanyDB; db = CompanyDB(); print(len(db.get_all_track_records()))"  # ~240건
```

---

### 6. 검증 기준

**생성 완료 후 체크리스트:**

**1. 회사소개서 PDF 품질:**
- ✅ 20개 회사 모두 PDF 생성 완료
- ✅ 각 PDF 10페이지 (표지~비전)
- ✅ 넥스트웨이브 템플릿 구조 일치
- ✅ 실제 정보 vs 합성 정보 비율 (70:30)
- ✅ 한글 폰트 정상 렌더링

**2. CompanyDB 데이터 무결성:**
- ✅ 실적: 총 240건 (회사당 평균 12건)
- ✅ 인력: 총 160명 (회사당 평균 8명)
- ✅ ChromaDB 저장 확인
- ✅ ID 중복 없음 (sha256 해시 충돌 체크)
- ✅ Metadata 필수 필드 완비

**3. 테스트 시나리오:**
- ✅ 10~15개 시나리오 정의 완료
- ✅ HIGH/LOW/MEDIUM MATCH 골고루 분포
- ✅ 각 시나리오 예상 결과 명확히 기술
- ✅ 검증 포인트 실행 가능

**4. E2E 플로우 검증 (샘플 1건):**
```bash
# TS-001 시나리오 실제 실행
curl -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  http://localhost:8000/api/upload_target?session_id=test_001

curl -F "file=@data/company_docs/삼성SDS_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=test_001

curl -X POST http://localhost:8000/api/analyze?session_id=test_001

# 결과 확인: GO/NO-GO 점수 90점 이상?
```

**5. 품질 메트릭:**
- PDF 파일 크기: 300KB~500KB (10페이지 기준)
- 실적 금액 범위: 10억~500억 (현실성)
- 인력 경력 범위: 3년~20년
- 자격증 분포: 회사 규모 대비 합리적

**6. 문서화:**
- ✅ `docs/test/TEST_SCENARIOS.md` 생성
- ✅ `docs/test/README.md` (더미 데이터 사용 가이드)
- ✅ `scripts/dummy_data/README.md` (재생성 방법)

---

## 다음 단계

1. **구현 계획 작성** (`writing-plans` 스킬)
2. **회사 프로필 큐레이션** (수동, 1~2시간)
3. **스크립트 구현** (PDF 생성, CompanyDB 적재)
4. **테스트 시나리오 실행** (E2E 검증)
5. **문서화 완성**

---

**승인:** 2026-03-08
**다음:** `docs/plans/2026-03-08-dummy-data-generation-impl-plan.md`
