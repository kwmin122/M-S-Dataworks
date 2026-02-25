# KiraBot 환경설정 페이지 통합 리디자인 + 회사정보 관리 시스템

## Goal

사이드바 내비를 3개로 단순화하고, Claude.ai 스타일 통합 설정 페이지를 구축하며, 회사 정보를 한 번 등록하면 채팅·발주예측·알림 전 기능에서 자동 활용되는 시스템을 만든다.

## 결정 사항

| 항목 | 결정 |
|------|------|
| 저장소 키 | username 기반 (`data/company_profiles/{username}/`) |
| 파일 크기 제한 | 무료 10MB / 유료 50MB |
| 이메일 발송 | 레거시 FastAPI에 Resend + openpyxl 추가 |
| 알림 설정 위치 | 사이드바에 유지 (설정 페이지에서 제외) |
| 구현 범위 | Part A~F 전체 |

---

## Part A: 백엔드 — 회사 프로필 API

### 저장소 구조

```
data/company_profiles/{username}/
  ├── profile.json          ← 구조화된 회사 정보
  └── documents/
      ├── doc_abc123_사업자등록증.pdf
      └── doc_def456_회사소개서.docx
```

### profile.json 스키마

```json
{
  "companyName": "M&S SOLUTIONS",
  "businessType": "소프트웨어개발",
  "businessNumber": "",
  "certifications": ["ISO 9001", "ISMS"],
  "regions": ["서울", "경기"],
  "employeeCount": 50,
  "annualRevenue": "30억",
  "keyExperience": ["공공SI", "데이터분석", "AI/ML"],
  "specializations": ["정보시스템 구축", "데이터 분석 플랫폼"],
  "documents": [
    {"id": "doc_abc123", "name": "사업자등록증.pdf", "uploadedAt": "2026-02-25T10:00:00Z", "size": 1024000}
  ],
  "aiExtraction": {
    "summary": "주요 실적: 공공SI 12건, 분석 5건. 보유 자격 3종. 활동 지역: 서울/경기.",
    "extractedAt": "2026-02-25T10:01:00Z",
    "raw": {}
  },
  "lastAnalyzedAt": "2026-02-25T10:01:00Z",
  "createdAt": "2026-02-25T10:00:00Z",
  "updatedAt": "2026-02-25T10:30:00Z"
}
```

### API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/api/company/profile` | GET | 프로필 조회 (쿠키 → username) |
| `/api/company/profile` | POST | 문서 업로드 + LLM 자동추출 (multipart) |
| `/api/company/profile` | PUT | 프로필 수동 편집 (JSON) |
| `/api/company/profile` | DELETE | 프로필 초기화 (문서 + JSON 전부 삭제) |
| `/api/company/documents/{doc_id}` | DELETE | 개별 문서 삭제 |
| `/api/company/reanalyze` | POST | 기존 문서 재분석 |

### 인증

모든 회사 프로필 API는 쿠키(`kira_auth`) → `resolve_user_from_session()` → username 추출.
미인증 시 401 Unauthorized.

### LLM 자동 추출 로직

1. 업로드된 파일 → `document_parser.py`로 텍스트 추출
2. 추출된 텍스트 → OpenAI에 구조화 정보 추출 요청 (Structured Outputs)
3. 추출 결과 → profile.json의 각 필드에 머지 (기존값이 없는 필드만 채움)
4. `aiExtraction.summary`에 요약 텍스트 저장

### 벡터DB 연동

회사 문서 업로드 시 기존 세션 기반 벡터DB 외에 **유저별 영구 벡터 컬렉션**도 생성:
- 컬렉션명: `company_{username}`
- 채팅 세션 시작 시 이 컬렉션을 RAG 컨텍스트에 자동 포함

---

## Part B: 사이드바 변경

### 상단 내비 (4→3개)

```
채팅 | 알림 설정 | 발주예측
```

- "대시보드" 제거 (설정 > 사용량으로 흡수)

### 하단 프로필 영역

기존: 아바타+이름+이메일 + [홈][로그아웃] 버튼

변경: **프로필 영역 전체 클릭 → 바텀업 팝오버**

```
┌─────────────────────────┐
│ bill.min122@gmail.com   │  ← 이메일 (text-slate-400)
│─────────────────────────│
│ ⚙ 설정                  │  → /settings
│ 🏠 홈으로               │  → 랜딩 페이지
│─────────────────────────│
│ 🚪 로그아웃             │
└─────────────────────────┘
```

- 다크 배경 (bg-gray-800), rounded-lg, shadow-xl
- 외부 클릭 / ESC로 닫힘
- Framer Motion: translateY(8px) → 0, opacity 0→1
- 새 파일: `components/sidebar/ProfilePopover.tsx`

---

## Part C: 통합 설정 페이지

### 레이아웃 (Claude.ai 패턴)

```
┌──────────────────────────────────────────┐
│ ← 설정                                   │  ← 뒤로가기 (router.back() || /chat)
│                                          │
│  ┌────────┐  ┌──────────────────────────┐│
│  │ 일반    │  │                          ││
│  │ 회사정보│  │  (선택된 탭 콘텐츠)       ││
│  │ 사용량  │  │                          ││
│  │ 계정    │  │                          ││
│  └────────┘  └──────────────────────────┘│
└──────────────────────────────────────────┘
```

- 사이드바 숨김 (전체 화면)
- 좌측 탭: w-48, 선택 시 좌측 kira-500 바 + font-semibold
- 우측: flex-1, max-w-2xl mx-auto, overflow-y-auto
- React Router nested routes

### 라우트

```
/settings         → Navigate to /settings/general
/settings/general → SettingsGeneral
/settings/company → SettingsCompany
/settings/usage   → SettingsUsage
/settings/account → SettingsAccount
/dashboard        → Navigate to /settings/usage (하위호환)
```

### SettingsGeneral — 일반

- 프로필: 아바타, 이름, 이메일 (읽기전용, Google OAuth 정보)
- 모양: 테마 라디오 (시스템/라이트/다크) — UI만, 기능은 이후

### SettingsCompany — 회사 정보 ⭐

3개 섹션:

1. **회사 프로필 폼**
   - 회사명 (input), 업종 (input), 사업자번호 (input)
   - 자격증 (ChipInput), 지역 (ChipInput), 전문분야 (ChipInput)
   - 직원수 (number), 연매출 (input)
   - 주요경험 (ChipInput)
   - [프로필 저장] 버튼 → `PUT /api/company/profile`

2. **등록 문서**
   - 파일 목록 (이름, 크기, 업로드일, [삭제])
   - 드래그&드롭 업로드 영역 (PDF, DOCX, HWP, TXT, MD, PPT 지원)
   - 파일 크기 제한: 무료 10MB / 유료 50MB

3. **AI 추출 역량 요약**
   - 문서에서 자동 추출된 요약 텍스트
   - [재분석] → `POST /api/company/reanalyze`
   - [프로필에 반영] → 추출값으로 폼 필드 채움

### SettingsUsage — 사용량

기존 DashboardPage 내용 이전:
- 요약 카드 4개 (새 맞춤 공고, 마감 임박, GO 판정, 분석 완료)
- Smart Fit Top 5 (플레이스홀더)
- 알림 상태 카드 (활성/비활성 + 키워드)

### SettingsAccount — 계정

- 로그인 정보 (Google 계정 이메일)
- [로그아웃] 버튼
- 위험 구역: [계정 삭제] (확인 다이얼로그)

---

## Part D: 알림 이메일 엑셀 발송

### 레거시 백엔드에 추가

패키지: `resend`, `openpyxl`

### 엑셀 컬럼 (사용자 지정)

| 구분 | 공고명 | 수요처 | 부서 | 예산금액 | 공고 게시일시 | 입찰서 제출일시 | 입찰서 마감일시 | 낙찰방법 | 비고 |
|------|--------|--------|------|----------|--------------|----------------|----------------|----------|------|

### 발송 플로우

1. 알림 설정에 등록된 키워드/카테고리/지역/금액 조건으로 나라장터 검색
2. 매칭 결과 → openpyxl로 엑셀 파일 생성 (메모리)
3. Resend API로 이메일 발송 (엑셀 첨부)
4. 환경변수: `RESEND_API_KEY`, `RESEND_FROM_EMAIL`

### 스케줄러

- APScheduler 또는 간단한 asyncio 백그라운드 태스크
- 설정된 시간(매일 1~3회)에 실행
- `daily_1`: 지정 시간 1회, `daily_2`: 2회, `daily_3`: 3회

---

## Part E: 채팅 연동

### 세션 시작 시

1. `GET /api/company/profile` 호출
2. 프로필 존재 → conversation state에 `companyProfile` 저장
3. 채팅 헤더에 "🏢 {companyName} 연동됨" 뱃지 표시

### 분석 플로우 변경

- 프로필 있을 때: "회사 문서 먼저 등록" 단계 자동 스킵
- 프로필 없을 때: 기존 플로우 + "💡 설정 > 회사 정보에서 등록하면 매번 업로드 없이 자동 분석됩니다" 안내

### 백엔드 연동

입찰 분석 API 호출 시 company_profile 데이터를 context에 포함하여
LLM이 "이 입찰 공고가 우리 회사에 적합한지" 판단.

---

## Part F: 발주예측 연동

### 맞춤 추천 섹션

회사 프로필 존재 시 발주예측 페이지 상단에:
- "🏢 {companyName} 맞춤 추천" 제목
- 업종/지역/경험 기반 관련 기관 자동 추천 (최대 5개)

### 적합도 뱃지

검색 결과 발주계획에 표시:
- 🟢 높음: 업종 + 지역 + 실적 모두 매칭
- 🟡 보통: 일부 매칭
- ⚪ 미확인: 매칭 정보 부족

---

## 구현 순서

| 순서 | 파트 | 내용 |
|------|------|------|
| 1 | B | 사이드바 내비 3개 + 프로필 팝오버 |
| 2 | C-1 + D | SettingsPage 레이아웃 + 라우팅 |
| 3 | C-2 | SettingsGeneral |
| 4 | C-5 | SettingsUsage (대시보드 이전) |
| 5 | C-6 | SettingsAccount |
| 6 | A | 백엔드 회사 프로필 API |
| 7 | C-3 | SettingsCompany UI + API 연동 |
| 8 | D | 알림 이메일 엑셀 발송 (Resend + openpyxl) |
| 9 | E | 채팅 연동 |
| 10 | F | 발주예측 연동 |

## 기술 스택

- 프론트: React 19 + TypeScript + Vite + Tailwind CSS + Framer Motion + React Router v6
- 백엔드: FastAPI + document_parser.py + OpenAI (Structured Outputs)
- 이메일: Resend + openpyxl
- 저장: 파일시스템 (JSON + 문서) + ChromaDB (벡터)
