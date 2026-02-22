# Phase 8 설계 문서 — Kira Bot 올라운더 (2026-02-22)

**범위:** Phase 1~7(수집/분석/평가 인프라) 위에 사용자 가치 중심 기능 7개 추가
**포지셔닝:** `클라이언트형 수집 + 조달 분석 + 전략 판단 + 문서 생성 + 대화형 UX = Kira Bot 올라운더`
**참조:** `docs/plans/로드맵.md`, `키라봇.png`, `키라봇내부.png`, 나라장터 공고 확인 가이드.xlsx

---

## 1. 기존 사이트 분석 (UI/UX 현황)

### 랜딩 페이지 (키라봇.png)
- **헤더:** M&S Solutions 로고 + Product/Solutions/Pricing 내비게이션 + 로그인 버튼
- **히어로:** "복잡한 RFx 분석, KiraBot으로 빠르고 정확하게" — 블루/퍼플 그라디언트 ORB
- **기능 섹션:** 문서 업로드 & 분석, PDF 기반 질문답변, 근거 바로보기, 규정 검토, 보고서 생성
- **유스케이스:** 공공 입찰(RFP), 계약 검토, 법규/규정, 세금 보고서 사진 카드 4개
- **프라이싱:** Free(0원) / Pro(150,000원) / Enterprise(별도 협의)

### 워크스페이스 내부 (키라봇내부.png)
- **좌측 패널:** "회사 문서" 헤더, 탭(회사 문서 보기 / 분석 문서 보기), 문서 미리보기 영역
- **우측 패널 (Kira 워크스페이스):**
  - 파일 업로드 2개: [회사 문서 등록] + [분석 문서 등록]
  - [분석 실행] 버튼 (파란색 primary)
  - 채팅 영역: AI 인사 메시지
  - 퀵액션 칩 4개: 핵심 역량 / 요건 요약 / 준비 순서 / 체크리스트
  - 채팅 입력창 + 전송 버튼

**Phase 8 설계는 이 기존 Split-Pane 레이아웃을 보존하고 새 탭을 추가하는 방향으로 진행한다.**

---

## 2. 경쟁사 분석 및 차별화

| 기능 | 클라이원트 | 지투비플러스 | 조달AI | 고비드 | **Kira Bot** |
|---|---|---|---|---|---|
| 나라장터 공고 검색 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 인터뷰형 조건 입력 | ❌ | ❌ | ❌ | ❌ | **✅ Phase 8** |
| 다중 공고 동시 평가 | ❌ | ❌ | 부분 | ❌ | **✅ Phase 8** |
| 첨부파일 본문 검색 | ❌ | ❌ | ✅ | ❌ | **✅ Phase 8** |
| GO/NO-GO + 근거 | ❌ | ❌ | 부분 | ❌ | **✅ Phase 7** |
| 엑셀 일괄 다운로드 | ❌ | 부분 | ❌ | ❌ | **✅ Phase 8** |
| 발주계획 사전감지 | ❌ | ❌ | ❌ | ❌ | **✅ Phase 8** |
| 제안서 초안 자동 생성 | ❌ | ❌ | ❌ | ❌ | **✅ Phase 8** |
| 회사 강점 분석 카드 | ❌ | ❌ | ❌ | ❌ | **✅ Phase 8** |
| HWP 업로드/분석/생성 | ❌ | ❌ | 부분 | ❌ | **✅ Phase 8** |
| 민간입찰/HR/법무 확장 | ❌ | ❌ | ❌ | ❌ | **Phase 9+** |

---

## 3. Phase 8 모듈 상세 설계

### Module 1 — 스마트 공고 검색 (인터뷰 + 폼 하이브리드)

**사용자 페인포인트:** 나라장터 상세 검색 조건(지역, 업종, 기간, 금액, 마감 제외 등)을 매번 수동으로 설정해야 함.

**핵심 경험:**
- 워크스페이스 상단 탭에 **"공고 검색"** 탭 추가
- 진입 시 두 가지 모드 선택 제공:
  - **인터뷰 모드:** Kira가 대화로 조건 완성 (초보자용)
  - **폼 모드:** 숙련 사용자가 한번에 조건 입력 (세진테크 워크플로우 기반)

**인터뷰 모드 대화 플로우:**
```
Kira: "안녕하세요! 어떤 업종의 공고를 찾으시나요? (예: 통신, CCTV, 전기, 건설)"
User: "통신이랑 CCTV 관련"
Kira: "어느 지역 공고를 보실까요? (전체/특정 지역 선택)"
User: "경기도"
Kira: "금액 범위가 있으신가요? (예: 5천만~3억)"
User: "상관없어요"
Kira: "기간은 얼마나 보실까요? (최근 1주/1개월/3개월)"
User: "1개월"
Kira: "마감된 공고는 제외할까요?"
User: "네"
Kira: "조건을 저장해드릴까요? → [저장 후 검색] [바로 검색]"
```

**폼 모드 (나라장터 공고 확인 가이드 기반):**
```
┌─────────────────────────────────────────────────┐
│ 공고 검색 조건                           [저장] │
├─────────────────────────────────────────────────┤
│ 키워드    [통신] [CCTV] [영상감시] [+추가]      │
│ 지역      [경기도 ▼]                            │
│ 금액 범위 [최소 ______] ~ [최대 ______] 원      │
│ 기간      [● 최근 1개월] ○ 3개월 ○ 직접입력    │
│ 마감 제외 [✓ 마감된 공고 제외]                 │
│ 업종 구분 [정보통신 ▼] [전기공사 ▼]            │
│                                                 │
│              [검색하기]                         │
└─────────────────────────────────────────────────┘
```

**저장된 조건:** 회사 프로필의 `interestConfig`에 저장 → 이후 일일 자동 검색/평가에 활용

---

### Module 2 — 다중 공고 분석 + 엑셀 출력

**핵심 경험:**
- 검색 결과 N개 공고를 한 번에 GO/NO-GO 평가
- 결과를 표(카드 뷰/테이블 뷰) + 엑셀 다운로드로 제공

**결과 화면 레이아웃:**
```
공고 검색 결과  15건 발견  [엑셀 다운로드 ↓]  [카드뷰 | 테이블뷰]

┌────────────────────────────────────────────────────────────────┐
│ # │ 공고명              │ 금액   │ 마감    │ 지역  │ 판정  │ 액션 │
├────────────────────────────────────────────────────────────────┤
│ 1 │ 경기도청 CCTV...    │ 2.3억  │ 03/15  │ 경기  │ ✅ GO │ 상세 │
│ 2 │ 수원시 통신망...    │ 8천만  │ 03/12  │ 경기  │ ❌ NO │ 사유 │
│ 3 │ 용인시 영상감시...  │ 1.5억  │ 03/20  │ 경기  │ ✅ GO │ 상세 │
└────────────────────────────────────────────────────────────────┘
```

**엑셀 컬럼 (표준):** 공고명 / 금액 / 마감일 / 지역 / GO·NO-GO / 판정근거 / 부족조건 / 준비액션 / 공고URL

**카드 뷰:** 각 공고를 카드로 표시, GO는 초록 테두리, NO-GO는 회색, 부족조건은 오렌지 태그

**NO-GO 상세 사유 드로어:**
```
❌ NO-GO 판정 근거
- 부족 조건: 정보통신공사업 면허 미보유 (공고 요건: 필수)
- 준비 액션: 정보통신공사업 면허 취득 검토 또는 컨소시엄 입찰 고려
- 재평가: [조건 변경 후 재평가]
```

---

### Module 3 — 첨부파일 전문 검색 (조달AI 수준)

**핵심 경험:**
- 나라장터 공고의 제목이 아닌 HWP/PDF **본문 내용** 기준 검색
- "CCTV"가 제목에 없어도 첨부 입찰공고서 본문에 있으면 발견

**데이터 파이프라인:**
```
IngestionJob → HWP/PDF 다운로드 → 텍스트 추출
  → BidNotice.attachmentText 저장
  → Elasticsearch(또는 PostgreSQL FTS) 인덱싱
  → 검색 시 full-text search 병행
```

**UI 표시:**
- 검색 결과에 "첨부문서 본문 매칭" 배지 표시
- 매칭된 문장 하이라이트 스니펫 제공

---

### Module 4 — 발주계획 사전감지

**핵심 경험:**
- 나라장터 사전공개목록(사전규격/예산계획) 크롤링
- 실제 공고 게시 전 단계에서 선제 알림

**사전감지 알림 예시:**
```
🔔 [사전감지] 경기도청 CCTV 교체사업 예정
발주 예정: 2026-03-15 ~ 2026-04-30 (추정)
예산 규모: 약 2억원 (예산서 기준)
→ [상세 보기] [관심 등록]
```

**데이터 소스:**
- 조달청 사전공개 시스템 (www.g2b.go.kr 사전규격)
- 열린재정 Open API (기획재정부 예산 데이터)

---

### Module 5 — 제안서 초안 자동 생성

**핵심 경험:**
1. "제안서 초안 만들어드릴까요?" 안내
2. 회사 기존 템플릿 HWP/DOCX 업로드 요청
3. 공고 요건을 분석하여 템플릿 섹션별 자동 채움
4. HWP/DOCX 결과물 다운로드

**제안서 생성 워크플로우:**
```
공고 선택 → [제안서 초안 생성] 버튼
  → "회사 제안서 템플릿을 업로드해 주세요" 안내
  → 템플릿 업로드 (HWP/DOCX)
  → AI 분석:
      - 공고 요건 추출
      - 회사 프로필(면허/실적/인증) 매핑
      - 템플릿 섹션 식별
      - 섹션별 초안 생성
  → 미리보기 (좌측: 원본 템플릿, 우측: 생성된 초안)
  → 인라인 편집 + 다운로드
```

**워크스페이스 레이아웃 (제안서 탭):**
```
┌──────────────────────┬────────────────────────────┐
│ 템플릿 미리보기      │ Kira 제안서 워크스페이스   │
│                      │                            │
│ 1. 사업 개요         │ [공고 선택: 경기도 CCTV]   │
│ 2. 수행 전략         │ [템플릿 선택] [생성 실행]  │
│ 3. 수행 조직         │                            │
│ 4. 유사 실적         │ ─── 생성 완료 ──────────   │
│ 5. 가격 제안         │ 1. 사업 개요: 본 사업은... │
│                      │ 2. 수행 전략: 당사는...    │
│                      │                            │
│                      │ [편집] [다운로드 HWP/DOCX] │
└──────────────────────┴────────────────────────────┘
```

---

### Module 6 — 회사 강점 분석 + 공고 요약 카드

**핵심 경험:**
- 회사 정보 입력 → AI가 즉시 강점 분석 리포트 생성
- 선택한 공고에 대해 "우리 회사 강점 vs 공고 요구사항" 1페이지 카드

**강점 분석 카드 구성:**
```
┌─── 공고 요약 카드 (1페이지) ─────────────────────┐
│ 경기도청 CCTV 교체사업             마감: 03/15   │
│ 금액: 2.3억  지역: 경기  업종: 정보통신          │
├──────────────────────────────────────────────────┤
│ ✅ 우리 강점                  ⚠️ 보완 필요       │
│ - 정보통신공사업 면허 보유    - 시공실적 5억미만  │
│ - 경기도 지역 실적 3건        - 안전관리자 미등록 │
│ - CCTV 설치 인증(CC)                             │
├──────────────────────────────────────────────────┤
│ 판정: ✅ GO      준비 액션: 실적증명서 3건 준비  │
│ [제안서 초안 생성] [엑셀 저장] [공고 원문 보기]  │
└──────────────────────────────────────────────────┘
```

**회사 정보 입력 UI (온보딩/설정):**
- 업종, 면허 목록, 자본금, 주요 실적(최근 5건), 보유 인증, 활동 지역

---

### Module 7 — HWP 업로드/분석/문서 작성

**핵심 경험:**
- HWP 파일 업로드 → 자격요건 추출 (기존 rfx_analyzer 확장)
- HWP 형식 보존 상태로 문서 수정/작성

**HWP 처리 파이프라인:**
```
HWP 업로드 → python-hwp5 / HWP Open API 파싱
  → 텍스트 추출 → rfx_analyzer.analyze() 호출
  → 결과: constraints + 요약
  → 선택: HWP 형식으로 출력 (hwp5lib DOCX 변환 후 DOCX→HWP)
```

**지원 포맷:** HWP 5.x, HWPX, PDF, DOCX

---

## 4. 전체 UX 네비게이션 설계

### 워크스페이스 탭 구조

기존 워크스페이스의 우측 패널에 탭 추가:

```
┌──────────────────────────────────────────────────────────────┐
│ M&S Solutions     [Product] [Solutions] [Pricing]    [로그아웃]│
├──────────────────────────────────────────────────────────────┤
│                   │                                          │
│  회사 문서        │  [RFx 분석] [공고 검색] [다중 분석] [제안서]│
│  (좌측 패널)      │                                          │
│                   │  ← 선택한 탭 컨텐츠 ─────────────────   │
│  • 문서 미리보기  │                                          │
│  • 검색 결과 목록 │                                          │
│  • 제안서 초안    │                                          │
│  (탭에 따라 변경) │                                          │
│                   │                                          │
└──────────────────────────────────────────────────────────────┘
```

### 탭별 좌/우 패널 내용

| 탭 | 좌측 패널 | 우측 패널 |
|---|---|---|
| RFx 분석 (기존) | 회사 문서 미리보기 | 분석 문서 업로드 + 채팅 |
| 공고 검색 | 검색 결과 목록 / 공고 카드 | 인터뷰 채팅 or 폼 |
| 다중 분석 | 공고 테이블 (GO/NO-GO) | 필터 + 엑셀 다운로드 |
| 제안서 | 템플릿 미리보기 | 생성 제어 + 초안 편집 |

### 화면별 핵심 버튼 목록

**공고 검색 탭:**
- `[인터뷰로 검색]` / `[폼으로 검색]` — 모드 선택
- `[조건 저장]` — interestConfig에 저장
- `[검색하기]` — 파란색 primary
- `[첨부파일 포함 검색 ✓]` — 토글

**다중 분석 탭:**
- `[엑셀 다운로드 ↓]` — 오른쪽 상단 secondary 버튼
- `[카드뷰 | 테이블뷰]` — 토글 세그먼트
- `[상세 보기]` — 각 공고 행의 액션
- `[제안서 초안 생성]` — GO 공고 선택 후 활성화

**제안서 탭:**
- `[공고 선택]` — 드롭다운
- `[템플릿 업로드]` / `[기존 템플릿 사용]`
- `[초안 생성]` — 파란색 primary
- `[다운로드 HWP]` / `[다운로드 DOCX]`

**공고 카드:**
- `[GO 상세]` — 강점 분석 카드 드로어 오픈
- `[NO-GO 사유]` — 부족조건 드로어 오픈
- `[관심 등록 ★]` — 즐겨찾기

---

## 5. 데이터 모델 추가 (Phase 8)

### 신규 Prisma 모델

```prisma
model SavedSearch {
  id             String   @id @default(cuid())
  organizationId String   @map("organization_id")
  name           String
  conditions     Json     // 키워드[], 지역, 금액범위, 기간, 마감제외
  createdAt      DateTime @default(now()) @map("created_at")
  @@map("saved_searches")
}

model BidInterest {
  id             String   @id @default(cuid())
  organizationId String   @map("organization_id")
  bidNoticeId    String   @map("bid_notice_id")
  status         String   @default("STARRED") // STARRED | BIDDING | WON | LOST
  createdAt      DateTime @default(now()) @map("created_at")
  @@unique([organizationId, bidNoticeId])
  @@map("bid_interests")
}

model ProposalDraft {
  id             String   @id @default(cuid())
  organizationId String   @map("organization_id")
  bidNoticeId    String   @map("bid_notice_id")
  templateKey    String?  @map("template_key") // S3 key
  draftKey       String?  @map("draft_key")    // S3 key for generated file
  status         String   @default("PENDING")  // PENDING | GENERATING | DONE | ERROR
  createdAt      DateTime @default(now()) @map("created_at")
  updatedAt      DateTime @updatedAt @map("updated_at")
  @@map("proposal_drafts")
}

model PreBidSignal {
  id           String    @id @default(cuid())
  source       String
  externalId   String    @map("external_id")
  title        String
  estimatedAmt BigInt?   @map("estimated_amt")
  region       String?
  estimatedAt  DateTime? @map("estimated_at")
  createdAt    DateTime  @default(now()) @map("created_at")
  @@unique([source, externalId])
  @@map("pre_bid_signals")
}
```

---

## 6. API 설계 (Phase 8 신규 엔드포인트)

```
# 공고 검색
POST /api/search/bids
  body: { keywords, region, minAmt, maxAmt, period, excludeExpired, includeAttachmentText }
  returns: BidNotice[] + GO/NO-GO per organizationId

# 다중 평가 트리거
POST /api/evaluate/batch
  body: { bidNoticeIds: string[] }
  returns: EvaluationJob[] (async)

# 엑셀 내보내기
GET /api/export/evaluations.xlsx
  query: { organizationId, from, to, status }

# 제안서 초안 생성
POST /api/proposals
  body: { bidNoticeId, templateFile?: File }
  returns: ProposalDraft (status: PENDING)

GET /api/proposals/:id
  returns: ProposalDraft (status: DONE → draftKey)

# 회사 강점 카드
GET /api/strength-card/:bidNoticeId
  returns: { strengths, gaps, go, actionPlan }

# 발주계획 사전감지 목록
GET /api/pre-bid-signals
  query: { keywords[], region }
  returns: PreBidSignal[]
```

---

## 7. 릴리즈 Wave 계획 (로드맵.md 기반)

| Wave | 기간 | 모듈 | 출시 게이트 |
|---|---|---|---|
| Wave 1 | 4주 | Module 1 (스마트 검색) + Module 2 (다중분석/엑셀) | 검색→평가→엑셀 E2E 95% 성공 |
| Wave 2 | 4~6주 | Module 3 (FTS) + Module 6 (강점 카드) | FTS Recall 기준 충족 |
| Wave 3 | 6주 | Module 5 (제안서) + Module 7 (HWP) | 초안 생성 실패율 임계치 이하 |
| Wave 4 | 6주+ | Module 4 (사전감지) | 실공고 전환 정합성 검증 |

---

## 8. 기술 스택 추가 (Phase 8)

| 컴포넌트 | 기술 | 용도 |
|---|---|---|
| 첨부파일 FTS | PostgreSQL tsvector + GIN index | Module 3 본문 검색 |
| HWP 파싱 | python-hwp5 (olefile 기반) | Module 7 |
| 엑셀 생성 | exceljs (Node.js) | Module 2 |
| 파일 저장 | S3 / R2 | 템플릿·초안 저장 |
| 제안서 생성 | docxtemplater + pandoc → HWP | Module 5 |
| 사전감지 크롤러 | n8n + 조달청 사전공개 API | Module 4 |

---

## 9. KPI (Phase 8)

| 지표 | 목표 |
|---|---|
| TTFR (검색 시작→첫 결과) | < 10초 |
| 다중 평가 처리 속도 | 10건/분 이상 |
| 엑셀 내보내기 사용률 | 활성 조직의 60%+ |
| 첨부파일 검색 Recall | 0.80 이상 |
| 제안서 초안 생성 성공률 | 95%+ |
| HWP 파싱 성공률 | 90%+ |
| 사전감지 → 실공고 전환율 | 측정 후 목표 설정 |

---

## 10. 리스크 및 대응

| 리스크 | 대응 |
|---|---|
| HWP 파싱 실패 | python-hwp5 + 다중 폴백 (LibreOffice 변환) |
| 제안서 품질 편차 | 생성 결과에 근거/체크리스트 강제 출력 |
| 나라장터 API 변경 | n8n 워크플로우 모듈화, 오류 모니터링 |
| 사전감지 데이터 부정확 | "추정" 레이블 필수, 정확도 피드백 루프 |
| 엑셀 대용량 타임아웃 | 백그라운드 생성 + 다운로드 링크 이메일 발송 |
