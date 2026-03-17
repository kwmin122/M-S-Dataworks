# 랜딩 v2 — 2축 허브 + Studio 진입 설계

## 원칙

전부 구현, 전부 노출, 핵심 2개 강조.

---

## 정보구조

### 1차 축 (Hero CTA)

| 이름 | 목적 | 라우트 |
|------|------|--------|
| **공고 탐색** | 검색, 분석, 질의응답 | `/chat` |
| **입찰 문서 작성** | 제안서/수행계획서/PPT/실적기술서 생성 | `/studio` |

### 2차 축 (Hub 보조 카드)

| 이름 | 목적 | 라우트 |
|------|------|--------|
| 발주 예측 | 수요/발주 타이밍 판단 | `/forecast` |
| 회사 역량 관리 | 실적/인력/기술/스타일 자산 관리 | `/settings/company` |

---

## 레이아웃

### Hero 영역 (현재 Hero.tsx 수정)

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  100페이지 공고서,                                        │
│  AI가 3분 만에 읽고, 제안서까지 써줍니다.                  │
│                                                          │
│  공고를 읽고, 입찰 문서를 쓰는 가장 빠른 방법              │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────────┐           │
│  │  공고 탐색 시작   │  │  입찰 문서 작성 시작  │           │
│  │  (primary)       │  │  (secondary/accent)  │           │
│  └─────────────────┘  └─────────────────────┘           │
│                                                          │
│  맞춤 공고 알림 설정 →                                    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

- "무료로 시작하기" 1개 → 2개 CTA로 변경
- 공고 탐색: primary 버튼 (기존 스타일)
- 입찰 문서 작성: secondary 또는 accent 버튼 (구분되지만 동등)
- 알림 설정 링크는 그 아래 유지

### Hub Section (신규 — Hero 바로 아래)

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  ┌────────────────────────┐ ┌────────────────────────┐  │
│  │  🔍                    │ │  ✍️                    │  │
│  │  공고 탐색              │ │  입찰 문서 작성         │  │
│  │                        │ │                        │  │
│  │  나라장터 공고 검색,    │ │  제안서, 수행계획서,    │  │
│  │  분석, 질의응답을       │ │  PPT, 실적기술서를     │  │
│  │  빠르게 진행합니다.     │ │  Studio에서 생성하고   │  │
│  │                        │ │  개선합니다.            │  │
│  │  [시작하기 →]          │ │  [Studio 열기 →]       │  │
│  └────────────────────────┘ └────────────────────────┘  │
│                                                          │
│  ┌────────────────────────┐ ┌────────────────────────┐  │
│  │  📊 발주 예측          │ │  🏢 회사 역량 관리     │  │
│  │  발주 시기와 수요       │ │  실적, 인력, 기술,     │  │
│  │  흐름을 분석합니다.     │ │  스타일 자산을 관리     │  │
│  │  [둘러보기 →]          │ │  [설정 →]              │  │
│  └────────────────────────┘ └────────────────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

- 상단 2개: 더 큰 패딩, 더 큰 아이콘, 강조 border/shadow
- 하단 2개: 같은 카드 시스템, 크기만 한 단계 작게

---

## 디자인 토큰 (핀터레스트 스타일)

```css
/* 대형 카드 */
.hub-card-primary {
  padding: 2rem 2.5rem;          /* p-8 px-10 */
  border-radius: 1.25rem;        /* rounded-2xl */
  border: 1px solid slate-200;
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  transition: all 200ms;
}
.hub-card-primary:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.08);
}

/* 보조 카드 */
.hub-card-secondary {
  padding: 1.5rem 2rem;          /* p-6 px-8 */
  border-radius: 1rem;           /* rounded-xl */
  /* 나머지 동일, 크기만 축소 */
}
```

---

## Navbar 변경

### 데스크톱 (로그인 전)

```
[Logo M&S SOLUTIONS]  제품소개  활용사례  요금제     로그인  [Kira 시작하기]
```

### 데스크톱 (로그인 후)

```
[Logo M&S SOLUTIONS]  공고 탐색  입찰 문서 작성  알림  예측     [Avatar] 로그아웃
```

- 로그인 후: 제품소개/활용사례/요금제 → 실제 기능 링크로 교체
- "공고 탐색" → `/chat`
- "입찰 문서 작성" → `/studio`

---

## CTA 동작

| 상태 | 공고 탐색 | 입찰 문서 작성 |
|------|-----------|---------------|
| 비로그인 | 로그인 모달 → `/chat` | 로그인 모달 → `/studio` |
| 로그인 | `/chat` 즉시 이동 | `/studio` 즉시 이동 |
| Studio 미구현 | - | "곧 열립니다" badge + 비활성 또는 coming soon 모달 |

---

## 구현 Tasks

### Task L-1: ProductHub 컴포넌트

**신규:** `frontend/kirabot/components/landing/ProductHub.tsx`

- 4카드 그리드 (2열 × 2행)
- HubCard 컴포넌트: icon, title, description, cta, size(primary|secondary)
- 비로그인 시 클릭 → 로그인 모달
- 로그인 시 클릭 → 해당 라우트

### Task L-2: Hero 2-CTA 변경

**수정:** `frontend/kirabot/components/Hero.tsx`

- "무료로 시작하기" 1버튼 → "공고 탐색 시작" + "입찰 문서 작성 시작" 2버튼
- `onStart` → `onStartChat`, `onStartStudio` 2개 핸들러
- 카피 업데이트

### Task L-3: App.tsx 라우트 + 핸들러

**수정:** `frontend/kirabot/App.tsx`

- `/studio` 라우트 추가 (Phase 1 쉘 또는 coming soon)
- `handleStartStudio` 핸들러 (로그인 체크 → `/studio`)
- Hero에 2개 핸들러 전달

### Task L-4: Navbar 로그인 후 링크 변경

**수정:** `frontend/kirabot/components/Navbar.tsx`

- 로그인 후: 제품소개/활용사례/요금제 → 공고 탐색/입찰 문서 작성/알림/예측
- 각 링크 → 해당 라우트

### Task L-5: App.tsx에 ProductHub 삽입

**수정:** `frontend/kirabot/App.tsx`

- LandingPage에 `<ProductHub>` 삽입 (Hero 바로 아래, HowItWorks 위)

---

## 구현 순서

```
1. Task L-1: ProductHub + HubCard 컴포넌트 (독립)
2. Task L-2: Hero 2-CTA (onStartStudio 핸들러 필요)
3. Task L-3: App.tsx 라우트 + 핸들러
4. Task L-4: Navbar 변경
5. Task L-5: ProductHub 삽입
6. tsc --noEmit + 시각 확인
```
