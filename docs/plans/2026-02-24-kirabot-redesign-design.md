# KiraBot 대규모 리팩토링 & 기능 확장 — 설계 문서

**날짜**: 2026-02-24
**목적**: 챗봇 UI/UX를 Claude/ChatGPT 수준으로 리디자인하고, 입찰 플랫폼 차별화 기능을 추가하여 시장 돌풍을 일으킬 수 있는 제품으로 업그레이드.

---

## 1. 인프라 변경

### 1-1. React Router 도입

**현재**: `App.tsx`에서 `AppView` enum + `useState`로 뷰 전환 (URL 없음, 뒤로가기/딥링크 불가)

**변경**: `react-router-dom` v6 도입

```
/                      → 랜딩페이지 (현재 그대로 유지, 3D 이미지 포함)
/chat                  → 채팅 UI (기본 빈 대화 or 마지막 대화)
/chat/:conversationId  → 특정 대화 딥링크
/dashboard             → 입찰 대시보드 (신규)
/settings/alerts       → 맞춤 알림 설정 (신규)
/forecast              → 발주예측 (신규)
/privacy               → 개인정보처리방침
/terms                 → 이용약관
```

**인증 가드**:
- `/chat/*`, `/dashboard`, `/settings/*`, `/forecast` → `<ProtectedRoute>` 래퍼
- 미인증 시 `/`로 리다이렉트 + `LoginModal` 자동 트리거 (`?login=1` 쿼리 파라미터)
- 랜딩 페이지(`/`, `/privacy`, `/terms`)는 비인증 접근 가능

**마이그레이션**:
- `App.tsx`의 `AppView` FSM → `<BrowserRouter>` + `<Routes>` 교체
- `onNavigate()` → `useNavigate()` 훅으로 교체
- `sessionStorage` 뷰 저장 → URL 기반으로 자연스럽게 전환
- `ChatProvider`는 `/chat` 라우트 레이아웃 내에서만 마운트

**공유 레이아웃**:
```
/chat, /dashboard, /settings/*, /forecast
  → AppShell (공통 사이드바 + 메인 콘텐츠 영역)
    ├── Sidebar (네비게이션 + 대화목록)
    └── <Outlet /> (라우트별 콘텐츠)

/, /privacy, /terms
  → 랜딩 레이아웃 (Navbar + Footer)
```

### 1-2. Tailwind v4 로컬 설치

**현재**: CDN `<script>` 태그 + 런타임 config in `index.html`

**변경**: 로컬 설치로 전환
- `npm install tailwindcss @tailwindcss/postcss postcss`
- `postcss.config.js` + `tailwind.config.ts` 생성
- 기존 런타임 config의 색상/폰트 → `tailwind.config.ts`로 이전
- `src/index.css`에 `@import "tailwindcss"` 추가
- CDN `<script>` 제거
- 빌드 시 tree-shaking으로 번들 사이즈 대폭 축소

### 1-3. Framer Motion 도입

- `npm install framer-motion`
- `utils/animations.ts`에 공통 variants 정의:
  - `fadeIn`, `slideUp`, `slideDown`, `staggerContainer`, `pageTransition`
- `AnimatePresence`로 라우트 전환 애니메이션
- 개별 컴포넌트에서 `motion.div` 사용

### 1-4. 추가 패키지

- `react-router-dom` — URL 라우팅
- `framer-motion` — 애니메이션
- `recharts` — 발주예측 차트 (가볍고 React 친화적)
- 기존 패키지 유지: `lucide-react`, `react-pdf`

---

## 2. 색상 시스템 (챗 UI 전용)

### 디자인 원칙

**"블루 = 신뢰/전문성, 퍼플 포인트 = AI 지능"**

클라이원트가 보라-퍼플 계열을 브랜드로 사용 중이므로 차별화를 위해:
- **Primary**: 현재 랜딩의 블루 아이덴티티(`#1a4df5`)를 deep하게 확장
- **AI Accent**: 퍼플은 AI 생성 결과물(Smart Fit 점수, 인사이트, 제안서)에만 포인트로 사용
- **랜딩페이지**: 현재 색상 100% 유지

### 색상 팔레트 (`tailwind.config.ts`)

```typescript
colors: {
  // 기존 primary 유지 (랜딩페이지용)
  primary: {
    50: '#f2f6ff', 100: '#e6ecff', 200: '#cddbff',
    300: '#a3c0ff', 400: '#759dff', 500: '#4d7eff',
    600: '#2e65ff', 700: '#1a4df5', 800: '#143dba', 900: '#12328f',
  },
  // 챗 UI 전용 — 딥 블루-네이비 기반
  kira: {
    50:  '#eff6ff',  // 가장 밝은 블루
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6',  // 메인 액센트
    600: '#2563eb',  // 버튼 호버
    700: '#1d4ed8',  // 주요 버튼
    800: '#1e40af',
    900: '#1e3a8a',
    950: '#172554',  // 가장 어두운 네이비
  },
  // AI 결과물 전용 퍼플 포인트
  ai: {
    50:  '#faf5ff',
    100: '#f3e8ff',
    200: '#e9d5ff',
    400: '#c084fc',
    500: '#a855f7',  // AI 인사이트 배지
    600: '#9333ea',
    700: '#7e22ce',  // AI 강조
  },
  // 시맨틱
  go:    '#22c55e',  // GO 판정 (green-500)
  nogo:  '#ef4444',  // NO-GO 판정 (red-500)
  warn:  '#f59e0b',  // 부분 충족 (amber-500)
  // 서피스
  sidebar:       '#0f172a',  // 네이비 다크 (slate-900 대체)
  'sidebar-hover': '#1e293b', // slate-800
  'sidebar-active': '#1d4ed8', // kira-700
}
```

### 적용 매핑

| 요소 | 현재 | 변경 |
|------|------|------|
| 사이드바 배경 | `bg-slate-900` | `bg-sidebar` (#0f172a) |
| 사이드바 호버 | `bg-slate-800` | `bg-sidebar-hover` |
| 사이드바 활성 | `bg-primary-700/20` | `bg-sidebar-active/20` |
| 유저 메시지 | `bg-primary-700` | `bg-gradient-to-r from-kira-600 to-kira-700` |
| AI 메시지 | `bg-white border` | `bg-gradient-to-br from-kira-50 to-blue-50` |
| 버튼/CTA | `bg-primary-700` | `bg-kira-700 hover:bg-kira-800` |
| 칩 버튼 | `border-slate-200` | `bg-kira-50 text-kira-700 hover:bg-kira-100` |
| Smart Fit 점수 | — | `text-ai-600` + `stroke-ai-500` (퍼플 원형 프로그레스) |
| AI 인사이트 | — | `bg-ai-50 border-ai-200 text-ai-700` |
| GO 배지 | `bg-emerald-*` | `bg-go/10 text-go` |
| NO-GO 배지 | `bg-red-*` | `bg-nogo/10 text-nogo` |
| 카드 쉐도우 | `shadow-sm` | `shadow-md shadow-kira-500/5` (은은한 블루 그림자) |

---

## 3. 채팅 UI 리디자인

### 3-1. 사이드바 개선

**열린 상태 (240px)**:
```
┌──────────────────────┐
│ 🏠 KiraBot  [◀][+]  │  ← 로고, 접기, 새대화
│                      │
│ ─── 네비게이션 ────── │
│ 📊 대시보드            │  ← /dashboard 이동
│ 💬 채팅               │  ← /chat 이동
│ 🔔 알림 설정          │  ← /settings/alerts 이동
│ 📈 발주예측            │  ← /forecast 이동
│                      │
│ ─── 최근 대화 ─────── │
│ IT 용역 서울 검색      │  ← 자동 생성 제목
│ 도로공사 공고 분석     │
│ 소프트웨어 개발 입찰   │
│ ...                  │
│                      │
│ ─── 하단 ──────────── │
│ 👤 사용자명  [로그아웃] │
└──────────────────────┘
```

**닫힌 상태 (60px)**:
```
┌────┐
│ K  │  ← 로고 이니셜
│ [▶]│  ← 펼치기 (hover tooltip: "사이드바 열기")
│    │
│ 📊 │  ← hover tooltip: "대시보드"
│ 💬 │  ← hover tooltip: "채팅"
│ 🔔 │  ← hover tooltip: "알림 설정"
│ 📈 │  ← hover tooltip: "발주예측"
│ [+]│  ← hover tooltip: "새 대화"
│    │
│ 👤 │  ← hover tooltip: 사용자명
└────┘
```

**전환 애니메이션**: Framer Motion `animate={{ width }}` + `transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}`

### 3-2. 대화 제목 자동 생성

현재 모든 대화가 "새 대화"로 생성되어 사이드바가 무의미한 문제 해결.

**로직** (`useConversationFlow.ts`):
1. 첫 user 메시지가 push될 때 제목 자동 업데이트
2. 칩 클릭 → 선택한 기능명 ("공고 검색/분석", "문서 분석")
3. 텍스트 입력 → 첫 20자 + "..." (검색 키워드 기반)
4. 분석 완료 시 → 분석 문서 제목으로 업데이트 (기존 로직 유지)

### 3-3. 메시지 시스템 개선

- **AI 메시지 배경**: `bg-gradient-to-br from-kira-50 to-blue-50` (은은한 블루)
- **유저 메시지**: `bg-gradient-to-r from-kira-600 to-kira-700` + 흰 텍스트
- **메시지 등장 애니메이션**: Framer `slideUp` (opacity 0→1, y 20→0, 0.3s ease-out)
- **타이핑 인디케이터**: 3-dot bounce CSS animation (로딩 상태 대체)
- **스트리밍**: 현재 SSE 미지원이므로 로딩 스피너 유지 (향후 확장 가능)

### 3-4. 입력창 개선

- 하단 고정, **채팅 컬럼 내에서** `max-w-3xl` 중앙 정렬
- ContextPanel이 열려도 입력창은 채팅 영역 안에서만 중앙 유지
- `rounded-2xl` + `shadow-md` + 포커스 시 `ring-2 ring-kira-300 shadow-kira-500/10`
- 자동 높이 조절 (기존 `useAutoResize` 유지)

### 3-5. 마이크로 인터랙션

- **버튼 클릭**: `whileTap={{ scale: 0.97 }}` (Framer Motion)
- **카드 호버**: `whileHover={{ y: -2 }}` + shadow 확대
- **로딩 스켈레톤**: `@keyframes pulse` (회색 펄스)
- **페이지 전환**: `AnimatePresence` + fade-slide (opacity + translateY)
- **칩 버튼 호버**: `bg-kira-100` + `translateY(-1px)` + subtle shadow

---

## 4. 입찰 대시보드 (`/dashboard`)

### 레이아웃

```
┌────────────────────────────────────────────────────────┐
│  공유 사이드바  │              대시보드 메인              │
│               │                                        │
│               │  ┌───────── 상단 요약 카드 (4개) ────────┐│
│               │  │ 🆕 신규매칭 │ ⏰ 마감임박 │ ✅ GO판정 │ 📄 분석완료 ││
│               │  │   12건     │   3건     │  5건    │  28건    ││
│               │  │  [확인하기] │ [확인하기] │ [확인] │ [확인]  ││
│               │  └────────────────────────────────────┘│
│               │                                        │
│               │  ┌── Smart Fit Top 5 ──┐ ┌── 마감임박 ─┐│
│               │  │ 내 회사 기준 추천     │ │             ││
│               │  │ 1. 공고A  87점 ████  │ │ D-2 공고X   ││
│               │  │ 2. 공고B  82점 ███   │ │ D-3 공고Y   ││
│               │  │ 3. 공고C  76점 ███   │ │ D-5 공고Z   ││
│               │  └─────────────────────┘ └─────────────┘│
│               │                                        │
│               │  ┌── 주간 활동 요약 ───────────────────┐│
│               │  │ 검색 45건 │ 분석 12건 │ GO 5건      ││
│               │  └────────────────────────────────────┘│
└────────────────────────────────────────────────────────┘
```

### 요약 카드 동작
- 각 카드 클릭 → 해당 필터 적용된 목록으로 이동
- "신규 매칭" → `/chat`에서 최신 검색 결과 표시
- "마감 임박" → `/chat`에서 마감 D-7 이내 공고 필터
- "GO 판정" → 분석 완료 + GO 판정 결과 목록
- 카드 등장: Framer `staggerChildren` (순차 slide-up)

### Smart Fit Top 5
- **회사 문서 등록 시**: 적합도 순 Top 5 표시 + 원형 프로그레스 바
- **미등록 시 (Empty State)**:
  ```
  ┌─────────────────────────────────┐
  │   📄                            │
  │   회사 정보를 등록하면           │
  │   맞춤 추천을 받을 수 있습니다   │
  │                                 │
  │   [회사 문서 등록하기]           │
  └─────────────────────────────────┘
  ```

### 데이터 소스
- 기존 `kiraApiService` 확장: `/api/dashboard/summary` 엔드포인트 추가
- 백엔드에서 세션별 분석 결과 집계

---

## 5. 알림 설정 (`/settings/alerts`)

### 페이지 구조

```
┌─────────────────────────────────────────────────────┐
│  공유 사이드바  │  ⚙ 설정 > 공고 알림                 │
│               │                                      │
│               │  ┌── 자동 알림 ─────── [ON/OFF 토글] ─┐│
│               │  │  빈도: ● 즉시  ○ 1일1회  ○ 주간    ││
│               │  │  채널: [✓ 이메일] [□ 카카오톡]      ││
│               │  └────────────────────────────────────┘│
│               │                                      │
│               │  ── 알림 규칙 ──────────────────────── │
│               │                                      │
│               │  ┌── "IT 용역 서울" ────── [▼ 접기] ──┐│
│               │  │  포함: [소프트웨어✕] [IT✕] [용역✕]  ││
│               │  │  제외: [물품✕] [공사✕]              ││
│               │  │  업무: [✓용역] [□물품] [□공사] ...  ││
│               │  │  지역: [서울✕] [경기✕]              ││
│               │  │  금액: ──●──────●── 1억 ~ 10억     ││
│               │  │  발주기관: [한국도로공사✕]            ││
│               │  │                                    ││
│               │  │  📊 미리보기: 최근 7일 매칭 23건     ││
│               │  │  [활성 ON/OFF]                     ││
│               │  └────────────────────────────────────┘│
│               │                                      │
│               │  ┌── "공사 전국" ─────── [▶ 펼치기] ──┐│
│               │  │  요약: 공사 | 전국 | 5억~50억       ││
│               │  └────────────────────────────────────┘│
│               │                                      │
│               │  [+ 새 알림 규칙 추가]                 │
│               │                                      │
│               │  [저장]  [테스트 알림 발송]              │
└─────────────────────────────────────────────────────┘
```

### 규칙 시스템
- **다중 규칙**: 각 규칙은 독립 조건 (규칙 간 **OR** 합집합)
- **중복 매칭 처리**: 하나의 공고가 여러 규칙에 매칭돼도 알림은 **1회만** 발송 (서버에서 deduplicate)
- **규칙 이름**: 자동 생성 (첫 포함 키워드 + 업무구분 + 지역) 또는 수동 편집

### 키 컴포넌트
- **키워드 칩 입력**: `<ChipInput>` — 타이핑 → Enter → 칩 생성, X로 삭제
- **금액 슬라이더**: `<DualRangeSlider>` — 커스텀 dual handle, 값 라벨 표시
- **미리보기**: 조건 변경 시 debounce 500ms → `/api/alerts/preview` 호출 → 매칭 건수 표시
- **아코디언**: Framer `AnimatePresence` + `motion.div` (height auto 전환)
- **토글**: iOS 스타일 둥근 토글 (`<Toggle>` 컴포넌트)

### 기존 채팅 내 알림 설정과의 관계
- 채팅 내 간단 알림 설정 플로우는 **유지** (빠른 설정)
- 채팅에서 설정 완료 시 → 이 페이지의 규칙으로 자동 생성됨
- "고급 설정은 알림 설정 페이지에서 수정할 수 있습니다" 안내 메시지

---

## 6. 발주예측 (`/forecast`)

### MVP 전략

**초기**: 인기 기관 20개를 사전 집계해두고 UI 제공
**확장**: 검색 시 실시간 API 조회 → 점진적으로 기관 데이터 축적

### 페이지 레이아웃

```
┌────────────────────────────────────────────────────────┐
│  공유 사이드바  │  📈 발주예측                           │
│               │                                        │
│               │  [기관명 or 키워드 검색] [🔍 검색]       │
│               │                                        │
│               │  ── 인기 기관 바로가기 ──                │
│               │  [한국도로공사] [조달청] [LH] [KOTRA]    │
│               │                                        │
│               │  ┌── 한국도로공사 발주 패턴 ──────────┐  │
│               │  │ (recharts 타임라인 차트)            │  │
│               │  │ 2024 ──●──●──────●──               │  │
│               │  │ 2025 ●──●──●──────●──●             │  │
│               │  │ 2026 ●──●──■(예측)                 │  │
│               │  │       1  2  3  4  5  6  ...        │  │
│               │  └────────────────────────────────────┘  │
│               │                                        │
│               │  ┌── 🤖 AI 인사이트 ─────────────────┐  │
│               │  │ • 이 기관은 매년 3월 IT 용역 발주    │  │
│               │  │ • 예상 발주: 2건, 금액: 5억~10억     │  │
│               │  │ • 추천 준비 시기: 2026년 2월          │  │
│               │  │                                    │  │
│               │  │ ⚠ 참고용 — AI 예측은 과거 패턴 기반  │  │
│               │  └────────────────────────────────────┘  │
│               │                                        │
│               │  ┌── 이 기관 최근 공고 ──────────────┐  │
│               │  │ (공고 목록 테이블)                  │  │
│               │  └────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

### 데이터 파이프라인
1. **나라장터 API**: 기관별 과거 공고 조회 (`DATA_GO_KR_API_KEY` 기존 키 활용)
2. **백엔드 집계**: `/api/forecast/:orgName` → 월별/연별 발주 건수·금액 집계
3. **AI 인사이트**: 집계 데이터 → LLM 프롬프트 → 패턴 분석 텍스트 생성
4. **캐싱**: 기관별 집계 결과를 DB/파일에 캐싱 (1일 갱신)

### 경쟁분석 (공고 카드 통합)
- BidCardListView의 각 공고 카드에 **경쟁 강도 배지** 추가
- 높음🔴 / 보통🟡 / 낮음🟢 (과거 유사 공고 참여 업체 수 기반)
- "이 분야 평균 경쟁률: 4.2:1" 툴팁
- 데이터 불완전 시 "참고용" 표시 필수
- 데이터 소스: 나라장터 낙찰 정보 API

### Empty State (데이터 없는 기관)
```
┌─────────────────────────────┐
│   📈                        │
│   이 기관의 발주 데이터가     │
│   아직 수집되지 않았습니다    │
│                             │
│   데이터 수집을 요청하면      │
│   24시간 내 분석해드립니다    │
│                             │
│   [데이터 수집 요청]          │
└─────────────────────────────┘
```

---

## 7. Smart Fit 스코어

### 점수 공식
```
Smart Fit = 자격 매칭률(60%) + 키워드 일치도(20%) + 지역 가점(10%) + 실적 가점(10%)
```

### UI 표시
- 공고 카드 우측에 **원형 프로그레스 바** (SVG circle + stroke-dasharray)
- 점수 색상: 80+ `text-go`, 60-79 `text-warn`, <60 `text-nogo`
- 프로그레스 바 색상: `stroke-ai-500` (퍼플 → AI가 산출한 점수 강조)

### 상세 팝오버 (클릭 시)
```
┌─────────────────────────┐
│ Smart Fit 상세           │
│                         │
│ 자격요건  ✓ 85%   ████  │
│ 키워드    ✓ 92%   █████ │
│ 지역      ✓ 서울   100% │
│ 실적      ⚠ 2/3건  67% │
│                         │
│ 총점: 87 / 100          │
└─────────────────────────┘
```

### 회사 문서 미등록 시
점수 대신 **"등록 필요"** 배지 + "회사 문서를 등록하면 맞춤 점수를 확인할 수 있습니다" 툴팁

### 백엔드
- 기존 `matcher.py`의 `ConstraintEvaluator` 결과를 활용
- 새 API: `/api/smart-fit/score` (session_id, bid_notice_id → score breakdown)
- 검색 결과 목록에서 일괄 점수 계산 지원

---

## 8. AI 제안서 초안 (`/chat` 내 통합)

### 동작 플로우
1. 공고 분석 결과(AnalysisResultView)에 **"제안서 초안 생성"** 버튼 추가
2. 클릭 → `pushStatus('loading', '제안서 초안을 생성하고 있어요...')`
3. 백엔드 호출: `POST /api/generate-proposal` (기존 `rag_engine/proposal_generator.py`)
4. 결과 → ContextPanel에 `ProposalPreview` 표시 (기존 컴포넌트 확장)

### 내보내기 기능
- **1순위**: 마크다운 내보내기 (`.md` 다운로드) + 클립보드 복사
- **2순위**: `.docx` 내보내기 시도 (서버사이드 변환)
- ProposalPreview 상단에 [📋 복사] [⬇ MD 다운로드] [⬇ DOCX 다운로드] 버튼

### 제안서 구조 (기존 proposal_generator.py 기반)
- 사업 개요 요약
- 자격 요건 대응 표
- 기술 제안 골격
- 수행 일정(안)
- 투입 인력(안)

---

## 9. 공동도급 파트너 추천 — 후순위

외부 업체 DB(유료)가 필요하므로 이번 마일스톤에서는 **UI 목업만** 준비.
- AnalysisResultView에서 "NOT_MET" 항목 옆에 "파트너 찾기" 버튼 (비활성)
- 클릭 시 "Coming Soon — 파트너 매칭 서비스 준비 중입니다" 모달

---

## 10. 모든 페이지 Empty State 디자인

각 페이지별 빈 상태:

| 페이지 | Empty State |
|--------|-------------|
| 대시보드 | "아직 분석한 공고가 없습니다. 채팅에서 공고를 검색해보세요." + CTA |
| Smart Fit | "회사 문서를 등록하면 맞춤 점수를 확인할 수 있습니다." + CTA |
| 알림 설정 | "아직 알림 규칙이 없습니다." + [새 규칙 추가] CTA |
| 발주예측 | "기관명을 검색하여 발주 패턴을 확인하세요." + 인기 기관 칩 |
| 채팅 (새 대화) | WelcomeScreen (현재 구현 완료) |

---

## 11. 구현 우선순위

```
Phase 1 (인프라 + 기반): React Router + Tailwind v4 + Framer Motion + 색상 시스템
Phase 2 (챗 UI 리디자인): 사이드바 + 메시지 + 입력창 + 대화 제목 자동 생성
Phase 3 (플랫폼 전환): 대시보드 홈 + Smart Fit 스코어
Phase 4 (고급 기능): 알림 설정 페이지
Phase 5 (차별화): 발주예측 + 경쟁분석
Phase 6 (킬러 피처): AI 제안서 연동
```

---

## 12. 검증 방법

- 매 Phase 완료 시 `npm run build` 성공 확인
- React Router 전환 후 모든 기존 URL 동작 확인
- 색상 변경 후 랜딩페이지 영향 없음 확인 (3D 이미지 포함)
- Framer Motion 애니메이션이 성능 저하 없이 동작 확인
- 새 페이지 각각 Empty State + 데이터 있는 상태 모두 확인
- 모바일 반응형 (768px 이하) 레이아웃 확인

---

## 13. 파일 구조 (예상)

```
frontend/kirabot/
├── App.tsx                          ← BrowserRouter + Routes 교체
├── index.css                        ← Tailwind v4 import
├── tailwind.config.ts               ← 색상 시스템
├── postcss.config.js                ← Tailwind PostCSS
├── utils/
│   ├── animations.ts                ← Framer Motion variants
│   └── analytics.ts                 ← (기존)
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx             ← 공유 사이드바 + Outlet (신규)
│   │   ├── ProtectedRoute.tsx       ← 인증 가드 (신규)
│   │   └── LandingLayout.tsx        ← 랜딩 Navbar+Footer 래퍼 (신규)
│   ├── chat/                        ← (기존 + 개선)
│   │   ├── ChatLayout.tsx           ← ChatProvider + ChatArea + ContextPanel
│   │   ├── Sidebar.tsx              ← 네비게이션 아이콘 추가
│   │   ├── ChatArea.tsx             ← WelcomeScreen 조건부 렌더링 (기존)
│   │   ├── WelcomeScreen.tsx        ← (기존)
│   │   └── ...
│   ├── dashboard/                   ← (전부 신규)
│   │   ├── DashboardPage.tsx
│   │   ├── SummaryCard.tsx
│   │   ├── SmartFitTop5.tsx
│   │   ├── SmartFitCircle.tsx       ← SVG 원형 프로그레스
│   │   ├── DeadlineList.tsx
│   │   └── WeeklySummary.tsx
│   ├── settings/                    ← (전부 신규)
│   │   ├── AlertSettingsPage.tsx
│   │   ├── AlertRuleCard.tsx
│   │   ├── ChipInput.tsx
│   │   ├── DualRangeSlider.tsx
│   │   ├── Toggle.tsx
│   │   └── AlertPreview.tsx
│   ├── forecast/                    ← (전부 신규)
│   │   ├── ForecastPage.tsx
│   │   ├── OrgPatternChart.tsx      ← recharts 타임라인
│   │   ├── AiInsightCard.tsx
│   │   └── OrgRecentBids.tsx
│   └── shared/                      ← (신규 공통 컴포넌트)
│       ├── EmptyState.tsx
│       ├── CompetitionBadge.tsx
│       └── SmartFitBadge.tsx
```
