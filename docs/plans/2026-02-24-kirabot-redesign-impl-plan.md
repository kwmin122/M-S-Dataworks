# KiraBot 대규모 리팩토링 & 기능 확장 — 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** KiraBot을 챗봇에서 입찰 분석 플랫폼으로 업그레이드 — 모던 UI, 라우팅, 대시보드, 발주예측, Smart Fit, AI 제안서

**Architecture:** React Router v6로 페이지 기반 네비게이션, 공유 AppShell(사이드바+Outlet), Framer Motion 애니메이션, Tailwind v4 로컬 + 블루 기반 색상 시스템

**Tech Stack:** React 19, react-router-dom v6, framer-motion, recharts, Tailwind CSS v4, Vite 6, TypeScript 5.8

**Design Doc:** `docs/plans/2026-02-24-kirabot-redesign-design.md`

---

## Phase 1: 인프라 (React Router + Tailwind v4 + Framer Motion + 색상)

### Task 1.1: 패키지 설치

**Files:**
- Modify: `frontend/kirabot/package.json`

**Step 1: 패키지 설치**

```bash
cd frontend/kirabot
npm install react-router-dom framer-motion recharts
npm install -D tailwindcss @tailwindcss/postcss postcss autoprefixer
```

**Step 2: 설치 확인**

Run: `cd frontend/kirabot && npm ls react-router-dom framer-motion recharts tailwindcss`
Expected: 4개 패키지 정상 설치됨

**Step 3: Commit**

```bash
git add frontend/kirabot/package.json frontend/kirabot/package-lock.json
git commit -m "chore: add react-router, framer-motion, recharts, tailwind v4"
```

---

### Task 1.2: Tailwind v4 로컬 전환

**Files:**
- Create: `frontend/kirabot/postcss.config.js`
- Create: `frontend/kirabot/tailwind.config.ts`
- Create: `frontend/kirabot/src/index.css`
- Modify: `frontend/kirabot/index.html` — CDN 스크립트 제거, CSS 링크 교체
- Modify: `frontend/kirabot/index.tsx` — CSS import 추가

**Step 1: postcss.config.js 생성**

```javascript
// frontend/kirabot/postcss.config.js
export default {
  plugins: {
    '@tailwindcss/postcss': {},
    autoprefixer: {},
  },
};
```

**Step 2: tailwind.config.ts 생성**

기존 `index.html` 런타임 config에서 색상을 이전하고, 새 kira/ai/sidebar 색상 추가:

```typescript
// frontend/kirabot/tailwind.config.ts
import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './index.html',
    './**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Pretendard', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        // 기존 primary 유지 (랜딩페이지 호환)
        primary: {
          50: '#f2f6ff', 100: '#e6ecff', 200: '#cddbff',
          300: '#a3c0ff', 400: '#759dff', 500: '#4d7eff',
          600: '#2e65ff', 700: '#1a4df5', 800: '#143dba', 900: '#12328f',
        },
        // 챗 UI 전용 — 딥 블루 기반
        kira: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe',
          300: '#93c5fd', 400: '#60a5fa', 500: '#3b82f6',
          600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af',
          900: '#1e3a8a', 950: '#172554',
        },
        // AI 결과물 전용 퍼플 포인트
        ai: {
          50: '#faf5ff', 100: '#f3e8ff', 200: '#e9d5ff',
          400: '#c084fc', 500: '#a855f7', 600: '#9333ea', 700: '#7e22ce',
        },
        go: '#22c55e',
        nogo: '#ef4444',
        warn: '#f59e0b',
        surface: '#ffffff',
        background: '#f8fafc',
        sidebar: '#0f172a',
        'sidebar-hover': '#1e293b',
        'sidebar-active': '#1d4ed8',
      },
    },
  },
  plugins: [],
};

export default config;
```

**Step 3: src/index.css 생성**

```css
/* frontend/kirabot/src/index.css */
@import "tailwindcss";

/* Pretendard font is loaded via CDN in index.html */

body {
  font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  background-color: #f8fafc;
  color: #0f172a;
}

/* 스크롤바 숨김 유틸리티 */
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
```

**Step 4: index.html에서 CDN 제거 + CSS 참조 교체**

`index.html`에서:
1. `<script src="https://cdn.tailwindcss.com"></script>` 제거
2. `<script>tailwind.config = { ... }</script>` 전체 블록 제거
3. 기존 `<style>` 블록 제거 (index.css로 이전됨)
4. `<link rel="stylesheet" href="/index.css">` → `<link rel="stylesheet" href="/src/index.css">` 교체

**Step 5: index.tsx에 CSS import 추가**

```typescript
// frontend/kirabot/index.tsx 최상단에 추가
import './src/index.css';
```

**Step 6: 빌드 확인**

Run: `cd frontend/kirabot && npm run build`
Expected: 성공. 모든 Tailwind 클래스 정상 적용.

**Step 7: Commit**

```bash
git add frontend/kirabot/postcss.config.js frontend/kirabot/tailwind.config.ts \
  frontend/kirabot/src/index.css frontend/kirabot/index.html frontend/kirabot/index.tsx
git commit -m "feat: migrate Tailwind from CDN to v4 local install with new color system"
```

---

### Task 1.3: Framer Motion 공통 variants 정의

**Files:**
- Create: `frontend/kirabot/utils/animations.ts`

**Step 1: animations.ts 생성**

```typescript
// frontend/kirabot/utils/animations.ts
import type { Variants } from 'framer-motion';

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2 } },
};

export const slideUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
};

export const slideDown: Variants = {
  hidden: { opacity: 0, y: -10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.2, ease: 'easeOut' } },
};

export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25 } },
};

export const pageTransition: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: 'easeOut' } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.15 } },
};

export const sidebarTransition = {
  duration: 0.3,
  ease: [0.4, 0, 0.2, 1] as const,
};
```

**Step 2: Commit**

```bash
git add frontend/kirabot/utils/animations.ts
git commit -m "feat: add Framer Motion animation variants"
```

---

### Task 1.4: React Router 도입 — 라우트 구조 + ProtectedRoute

**Files:**
- Create: `frontend/kirabot/components/layout/ProtectedRoute.tsx`
- Create: `frontend/kirabot/components/layout/AppShell.tsx`
- Create: `frontend/kirabot/components/layout/LandingLayout.tsx`
- Modify: `frontend/kirabot/App.tsx` — FSM → BrowserRouter 교체
- Modify: `frontend/kirabot/types.ts` — AppView enum 유지 (하위호환)

**Step 1: ProtectedRoute.tsx 생성**

```typescript
// frontend/kirabot/components/layout/ProtectedRoute.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { User } from '../../types';

interface ProtectedRouteProps {
  user: User | null;
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ user, children }) => {
  const location = useLocation();

  if (!user) {
    // 미인증 시 랜딩으로 리다이렉트 + login 모달 트리거
    return <Navigate to={`/?login=1&redirect=${encodeURIComponent(location.pathname)}`} replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
```

**Step 2: AppShell.tsx 생성** — 앱 내 페이지 공유 레이아웃 (사이드바 + Outlet)

```typescript
// frontend/kirabot/components/layout/AppShell.tsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../chat/Sidebar';
import type { User } from '../../types';

interface AppShellProps {
  user: User | null;
  onLogout: () => void;
}

const AppShell: React.FC<AppShellProps> = ({ user, onLogout }) => {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar user={user} onLogout={onLogout} onHome={() => {}} />
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
};

export default AppShell;
```

**Step 3: LandingLayout.tsx 생성**

```typescript
// frontend/kirabot/components/layout/LandingLayout.tsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import Navbar from '../Navbar';
import Footer from '../Footer';
import type { User } from '../../types';

interface LandingLayoutProps {
  user: User | null;
  onNavigate: (path: string) => void;
  onLoginClick: () => void;
  onLogout: () => void;
}

const LandingLayout: React.FC<LandingLayoutProps> = ({ user, onNavigate, onLoginClick, onLogout }) => {
  return (
    <div className="min-h-screen bg-background">
      <Navbar user={user} onNavigate={onNavigate} onLoginClick={onLoginClick} onLogout={onLogout} />
      <Outlet />
      <Footer />
    </div>
  );
};

export default LandingLayout;
```

**Step 4: App.tsx를 BrowserRouter로 교체**

기존 `App.tsx`의 AppView FSM을 `<BrowserRouter>` + `<Routes>`로 완전 교체.

핵심 구조:
```typescript
// frontend/kirabot/App.tsx
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { ChatProvider } from './context/ChatContext';
import ProtectedRoute from './components/layout/ProtectedRoute';
import AppShell from './components/layout/AppShell';
// ... 기존 landing 컴포넌트 imports

function AppRoutes() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // ?login=1 쿼리 시 자동 로그인 모달
  useEffect(() => {
    if (searchParams.get('login') === '1') setIsLoginModalOpen(true);
  }, [searchParams]);

  // 기존 auth bootstrap 로직 유지 (getCurrentGoogleUser 등)
  // handleLogin, handleLogout 유지

  return (
    <>
      <Routes>
        {/* 랜딩 페이지 */}
        <Route path="/" element={<LandingPage user={user} ... />} />
        <Route path="/privacy" element={<><Navbar .../><PrivacyPolicy /><Footer /></>} />
        <Route path="/terms" element={<><Navbar .../><TermsOfService /><Footer /></>} />

        {/* 앱 내 페이지 — 인증 필요 + 공유 사이드바 */}
        <Route element={
          <ProtectedRoute user={user}>
            <ChatProvider>
              <AppShell user={user} onLogout={handleLogout} />
            </ChatProvider>
          </ProtectedRoute>
        }>
          <Route path="/chat" element={<ChatPage user={user} />} />
          <Route path="/chat/:conversationId" element={<ChatPage user={user} />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/settings/alerts" element={<AlertSettingsPage />} />
          <Route path="/forecast" element={<ForecastPage />} />
        </Route>

        {/* 404 → 랜딩 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <LoginModal isOpen={isLoginModalOpen} ... />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
```

**참고**: `ChatPage`는 기존 `ChatLayout` 내부 로직에서 `ChatProvider` 분리 + `Sidebar` 분리한 버전. Phase 2에서 상세 리팩토링.

**Step 5: 빈 플레이스홀더 페이지 생성** (Phase 3~6에서 구현)

```typescript
// frontend/kirabot/components/dashboard/DashboardPage.tsx
const DashboardPage = () => <div className="flex-1 p-8"><h1 className="text-2xl font-bold">대시보드</h1><p className="text-slate-500 mt-2">준비 중...</p></div>;
export default DashboardPage;

// frontend/kirabot/components/settings/AlertSettingsPage.tsx
const AlertSettingsPage = () => <div className="flex-1 p-8"><h1 className="text-2xl font-bold">알림 설정</h1><p className="text-slate-500 mt-2">준비 중...</p></div>;
export default AlertSettingsPage;

// frontend/kirabot/components/forecast/ForecastPage.tsx
const ForecastPage = () => <div className="flex-1 p-8"><h1 className="text-2xl font-bold">발주예측</h1><p className="text-slate-500 mt-2">준비 중...</p></div>;
export default ForecastPage;
```

**Step 6: ChatPage.tsx** — 기존 ChatLayout에서 분리

기존 `ChatLayout.tsx`의 `ChatLayoutInner`에서 `ChatProvider`와 `Sidebar`를 AppShell로 빼고, ChatArea + ContextPanel만 남긴 버전:

```typescript
// frontend/kirabot/components/chat/ChatPage.tsx
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useChatContext } from '../../context/ChatContext';
import { usePersistedConversations } from '../../hooks/usePersistedConversations';
import ChatArea from './ChatArea';
import ContextPanel from './ContextPanel';
import type { User } from '../../types';

interface ChatPageProps { user: User | null; }

const ChatPage: React.FC<ChatPageProps> = ({ user }) => {
  usePersistedConversations();
  const { state } = useChatContext();
  const hasPanelContent = state.contextPanel.type !== 'none';

  const [panelRatio, setPanelRatio] = useState(0.5);
  const isDragging = useRef(false);

  // 기존 ChatLayout의 마우스 드래그 로직 그대로 유지
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const sidebarWidth = state.sidebarCollapsed ? 60 : 240;
      const availableWidth = window.innerWidth - sidebarWidth;
      const panelWidth = window.innerWidth - e.clientX;
      const ratio = Math.max(0.25, Math.min(0.65, panelWidth / availableWidth));
      setPanelRatio(ratio);
    };
    const handleMouseUp = () => {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [state.sidebarCollapsed]);

  return (
    <>
      <div
        style={hasPanelContent ? { flex: `${1 - panelRatio}` } : undefined}
        className={hasPanelContent ? 'min-w-0 h-full overflow-hidden' : 'flex-1 min-w-0 h-full overflow-hidden'}
      >
        <ChatArea user={user} />
      </div>
      {hasPanelContent && (
        <>
          <div
            className="w-1 shrink-0 cursor-col-resize bg-slate-200 hover:bg-kira-300 active:bg-kira-400 transition-colors"
            onMouseDown={handleMouseDown}
          />
          <div style={{ flex: `${panelRatio}` }} className="min-w-0 h-full">
            <ContextPanel />
          </div>
        </>
      )}
    </>
  );
};

export default ChatPage;
```

**Step 7: Navbar 네비게이션 업데이트**

`Navbar.tsx`의 기존 `onNavigate(AppView.DASHBOARD)` → `navigate('/chat')` 등으로 변경.
`Hero.tsx`의 "무료로 시작하기" → `navigate('/chat')`.

**Step 8: Vite historyApiFallback 설정**

```typescript
// vite.config.ts에 추가 (SPA 라우팅 지원)
server: {
  // ...기존...
  historyApiFallback: true, // 이미 Vite 기본 동작이므로 별도 설정 불필요할 수 있음
}
```

실제로 Vite의 SPA fallback은 기본 활성이므로 별도 설정 불필요. 단, build output 배포 시 서버에서 fallback 설정 필요.

**Step 9: 빌드 확인**

Run: `cd frontend/kirabot && npm run build`
Expected: 성공

**Step 10: Commit**

```bash
git add frontend/kirabot/components/layout/ frontend/kirabot/components/chat/ChatPage.tsx \
  frontend/kirabot/components/dashboard/ frontend/kirabot/components/settings/ \
  frontend/kirabot/components/forecast/ frontend/kirabot/App.tsx
git commit -m "feat: migrate to React Router v6 with shared AppShell layout"
```

---

### Task 1.5: Sidebar 네비게이션 아이콘 추가

**Files:**
- Modify: `frontend/kirabot/components/chat/Sidebar.tsx`
- Modify: `frontend/kirabot/components/chat/SidebarHeader.tsx`

**Step 1: Sidebar.tsx에 네비게이션 항목 추가**

기존 구조 유지하면서 네비게이션 섹션 추가:
- `useNavigate()` + `useLocation()` 사용
- 아이콘: `LayoutDashboard`, `MessageSquare`, `Bell`, `TrendingUp` (from lucide-react)
- 접힌 상태: 아이콘만 + 호버 tooltip (`title` 속성)
- 열린 상태: 아이콘 + 라벨
- 현재 라우트 활성 표시: `bg-sidebar-active/20 text-white`

**Step 2: SidebarHeader.tsx에서 홈 버튼 → /dashboard 라우팅**

기존 `onHome` prop → `navigate('/dashboard')` 또는 `navigate('/')`.

**Step 3: 빌드 확인 + Commit**

---

## Phase 2: 챗 UI 리디자인

### Task 2.1: 사이드바 색상 교체 + 애니메이션

**Files:**
- Modify: `frontend/kirabot/components/chat/Sidebar.tsx` — `bg-slate-900` → `bg-sidebar`
- Modify: `frontend/kirabot/components/chat/SidebarHeader.tsx`
- Modify: `frontend/kirabot/components/chat/SidebarFooter.tsx`
- Modify: `frontend/kirabot/components/chat/ConversationList.tsx`

**변경 내용:**
1. 모든 `bg-slate-900` → `bg-sidebar`
2. 모든 `bg-slate-800` → `bg-sidebar-hover`
3. Framer Motion `motion.div`로 사이드바 래핑 (width 애니메이션)
4. 접힌 상태 아이콘에 `title` 속성으로 tooltip 추가

---

### Task 2.2: 메시지 버블 색상 리디자인

**Files:**
- Modify: `frontend/kirabot/components/chat/MessageBubble.tsx`

**변경 내용:**
1. Bot 메시지: `bg-white border border-slate-200` → `bg-gradient-to-br from-kira-50 to-blue-50 border border-kira-100`
2. User 메시지: `bg-primary-700` → `bg-gradient-to-r from-kira-600 to-kira-700`
3. Bot 아바타: 기존 유지 또는 `bg-kira-100` 배경
4. 메시지 등장: Framer `motion.div` + `slideUp` variant

---

### Task 2.3: 대화 제목 자동 생성

**Files:**
- Modify: `frontend/kirabot/hooks/useConversationFlow.ts`

**변경 내용:**

`handleUserText()`에서 첫 user 메시지 push 후 제목 자동 설정:
```typescript
// 첫 메시지 시 제목 자동 생성
if (conversation.title === '새 대화') {
  const autoTitle = text.length > 20 ? text.slice(0, 20) + '...' : text;
  updateConv({ title: autoTitle });
}
```

`handleAction()`의 `welcome_action`에서도:
```typescript
const welcomeLabel = { doc_analysis: '문서 분석', bid_search: '공고 검색', setup_alert: '알림 설정' };
if (conversation.title === '새 대화') {
  updateConv({ title: welcomeLabel[action.value] || '새 대화' });
}
```

분석 완료 시 분석 문서 제목으로 업데이트하는 기존 로직은 유지.

---

### Task 2.4: 입력창 + 칩 버튼 색상 리디자인

**Files:**
- Modify: `frontend/kirabot/components/chat/ChatInput.tsx`
- Modify: `frontend/kirabot/components/chat/WelcomeScreen.tsx`

**변경 내용:**
1. ChatInput 전송 버튼: `bg-primary-700` → `bg-kira-700 hover:bg-kira-800`
2. 포커스 링: `focus-within:border-primary-500` → `focus-within:border-kira-500 focus-within:ring-2 focus-within:ring-kira-200`
3. WelcomeScreen 칩 버튼: `border-slate-200 hover:border-primary-300` → `bg-kira-50 text-kira-700 hover:bg-kira-100 hover:shadow-md`
4. WelcomeScreen 전송 버튼: `bg-primary-700` → `bg-kira-700`

---

### Task 2.5: 타이핑 인디케이터 + 메시지 애니메이션

**Files:**
- Modify: `frontend/kirabot/components/chat/messages/StatusMessageView.tsx`
- Modify: `frontend/kirabot/components/chat/MessageList.tsx`
- Modify: `frontend/kirabot/src/index.css` — 타이핑 dot keyframes 추가

**변경 내용:**
1. `index.css`에 타이핑 dot 애니메이션 keyframes 추가
2. StatusMessageView의 `loading` 레벨: 3-dot bounce 인디케이터 추가
3. MessageList의 각 메시지: Framer `motion.div` + `slideUp` variant

---

### Task 2.6: 버튼/카드 호버 효과 + 색상 전환

**Files:**
- Modify: `frontend/kirabot/components/chat/messages/BidCardListView.tsx`
- Modify: `frontend/kirabot/components/chat/messages/AnalysisResultView.tsx`
- Modify: `frontend/kirabot/components/chat/messages/ButtonChoiceView.tsx`
- Modify: `frontend/kirabot/components/chat/ChatHeader.tsx`

**변경 내용:**
1. 모든 `bg-primary-*` → `bg-kira-*` 교체 (챗 UI 내)
2. 모든 `text-primary-*` → `text-kira-*` 교체
3. GO 배지: `bg-emerald-100 text-emerald-700` → `bg-go/10 text-go`
4. NO-GO 배지: `bg-red-100 text-red-700` → `bg-nogo/10 text-nogo`
5. 카드 hover: `whileHover={{ y: -2 }}` + `shadow-md`

---

## Phase 3: 대시보드 + Smart Fit 스코어

### Task 3.1: 백엔드 — 대시보드 요약 API

**Files:**
- Modify: `services/web_app/main.py` — `/api/dashboard/summary` 엔드포인트 추가

**엔드포인트:** `GET /api/dashboard/summary?session_id=xxx`

**응답:**
```json
{
  "newMatches": 12,
  "deadlineSoon": 3,
  "goCount": 5,
  "totalAnalyzed": 28,
  "recentSearches": [...],
  "smartFitTop5": [
    { "bid": {...}, "score": 87, "breakdown": {...} }
  ]
}
```

초기에는 세션 기반 로컬 데이터에서 집계. 향후 DB 기반으로 확장.

---

### Task 3.2: 백엔드 — Smart Fit 스코어 계산 API

**Files:**
- Modify: `services/web_app/main.py` — `/api/smart-fit/score` 엔드포인트 추가

**엔드포인트:** `POST /api/smart-fit/score`

**요청:**
```json
{
  "session_id": "...",
  "bid_notice_id": "...",
  "keywords": ["소프트웨어", "IT"]
}
```

**응답:**
```json
{
  "totalScore": 87,
  "breakdown": {
    "qualification": { "score": 85, "maxScore": 60 },
    "keywords": { "score": 92, "maxScore": 20 },
    "region": { "score": 100, "maxScore": 10 },
    "experience": { "score": 67, "maxScore": 10 }
  }
}
```

기존 `matcher.py`의 `ConstraintEvaluator` 결과를 활용하여 점수 산출.

---

### Task 3.3: SmartFitCircle.tsx — SVG 원형 프로그레스 컴포넌트

**Files:**
- Create: `frontend/kirabot/components/shared/SmartFitCircle.tsx`

**구현:**
- SVG `<circle>` + `stroke-dasharray`로 원형 프로그레스 바
- Props: `score: number`, `size?: number`
- 색상: 80+ `stroke-go`, 60-79 `stroke-warn`, <60 `stroke-nogo`
- 중앙 텍스트: 점수 숫자

---

### Task 3.4: EmptyState.tsx — 공통 빈 상태 컴포넌트

**Files:**
- Create: `frontend/kirabot/components/shared/EmptyState.tsx`

**Props:** `icon`, `title`, `description`, `actionLabel?`, `onAction?`

---

### Task 3.5: DashboardPage.tsx 구현

**Files:**
- Modify: `frontend/kirabot/components/dashboard/DashboardPage.tsx` (플레이스홀더 교체)
- Create: `frontend/kirabot/components/dashboard/SummaryCard.tsx`
- Create: `frontend/kirabot/components/dashboard/SmartFitTop5.tsx`
- Create: `frontend/kirabot/components/dashboard/DeadlineList.tsx`
- Create: `frontend/kirabot/components/dashboard/WeeklySummary.tsx`
- Modify: `frontend/kirabot/services/kiraApiService.ts` — dashboard API 함수 추가

**구현:**
- 상단 4개 요약 카드 (Framer staggerChildren)
- Smart Fit Top 5 (회사 문서 미등록 시 EmptyState)
- 마감 임박 공고 목록
- 주간 활동 요약

---

### Task 3.6: Smart Fit 배지를 공고 카드에 추가

**Files:**
- Create: `frontend/kirabot/components/shared/SmartFitBadge.tsx`
- Modify: `frontend/kirabot/components/chat/messages/AnalysisResultView.tsx`

**변경 내용:**
- AnalysisResultView 헤더에 Smart Fit 원형 점수 표시
- 클릭 시 상세 breakdown 팝오버

---

## Phase 4: 알림 설정 페이지

### Task 4.1: 백엔드 — 알림 규칙 CRUD API

**Files:**
- Modify: `services/web_app/main.py`

**엔드포인트:**
- `GET /api/alerts/rules` — 규칙 목록 조회
- `POST /api/alerts/rules` — 규칙 생성
- `PUT /api/alerts/rules/:id` — 규칙 수정
- `DELETE /api/alerts/rules/:id` — 규칙 삭제
- `POST /api/alerts/preview` — 조건 미리보기 (매칭 건수)
- `POST /api/alerts/test` — 테스트 알림 발송

---

### Task 4.2: 공통 컴포넌트 — ChipInput, DualRangeSlider, Toggle

**Files:**
- Create: `frontend/kirabot/components/shared/ChipInput.tsx`
- Create: `frontend/kirabot/components/shared/DualRangeSlider.tsx`
- Create: `frontend/kirabot/components/shared/Toggle.tsx`

**ChipInput:** 텍스트 입력 → Enter → 칩 추가, X로 삭제
**DualRangeSlider:** 양쪽 핸들 range slider, 값 라벨 표시
**Toggle:** iOS 스타일 둥근 토글

---

### Task 4.3: AlertSettingsPage.tsx 구현

**Files:**
- Modify: `frontend/kirabot/components/settings/AlertSettingsPage.tsx` (플레이스홀더 교체)
- Create: `frontend/kirabot/components/settings/AlertRuleCard.tsx`
- Create: `frontend/kirabot/components/settings/AlertPreview.tsx`
- Modify: `frontend/kirabot/services/kiraApiService.ts` — alerts API 함수 추가

**구현:**
- 자동 알림 ON/OFF 토글 + 빈도/채널 설정
- 알림 규칙 카드 목록 (아코디언, Framer AnimatePresence)
- 키워드 칩 입력 (포함/제외)
- 금액 슬라이더
- 실시간 미리보기 (debounce 500ms)
- 저장 + 테스트 발송 버튼

---

## Phase 5: 발주예측 + 경쟁분석

### Task 5.1: 백엔드 — 발주예측 API

**Files:**
- Modify: `services/web_app/main.py`
- Modify: `services/web_app/nara_api.py` — 기관별 과거 공고 조회 함수 추가

**엔드포인트:**
- `GET /api/forecast/:orgName` — 기관별 발주 패턴 데이터
- `GET /api/forecast/popular` — 인기 기관 20개 목록

**응답:**
```json
{
  "orgName": "한국도로공사",
  "yearlyPattern": {
    "2024": [{"month": 1, "count": 2, "totalAmt": 500000000}, ...],
    "2025": [...],
    "2026": [...]
  },
  "aiInsight": "이 기관은 매년 3월에 IT 용역을 발주하는 패턴...",
  "recentBids": [...]
}
```

---

### Task 5.2: ForecastPage.tsx 구현

**Files:**
- Modify: `frontend/kirabot/components/forecast/ForecastPage.tsx` (플레이스홀더 교체)
- Create: `frontend/kirabot/components/forecast/OrgPatternChart.tsx` — recharts 타임라인
- Create: `frontend/kirabot/components/forecast/AiInsightCard.tsx`
- Create: `frontend/kirabot/components/forecast/OrgRecentBids.tsx`
- Modify: `frontend/kirabot/services/kiraApiService.ts` — forecast API 함수 추가

**구현:**
- 검색바 + 인기 기관 칩 버튼
- 타임라인 차트 (recharts ScatterChart)
- AI 인사이트 카드 (ai-50 배경, "참고용" 배지)
- 최근 공고 목록 테이블

---

### Task 5.3: 경쟁 강도 배지 — 공고 카드 통합

**Files:**
- Create: `frontend/kirabot/components/shared/CompetitionBadge.tsx`
- Modify: `frontend/kirabot/components/chat/messages/BidCardListView.tsx`
- Modify: `frontend/kirabot/types.ts` — BidNotice에 `competitionLevel?` 필드 추가

**변경 내용:**
- BidNotice 타입에 `competitionLevel?: 'high' | 'medium' | 'low'` 추가
- 공고 제목 옆에 CompetitionBadge 표시
- 데이터 불완전 시 "참고용" tooltip

---

## Phase 6: AI 제안서 연동

### Task 6.1: 제안서 생성 버튼 + 액션 추가

**Files:**
- Modify: `frontend/kirabot/types.ts` — `MessageAction`에 `generate_proposal` 추가
- Modify: `frontend/kirabot/components/chat/messages/AnalysisResultView.tsx`
- Modify: `frontend/kirabot/hooks/useConversationFlow.ts` — `generate_proposal` 핸들러

**변경 내용:**
1. AnalysisResultView에 "제안서 초안 생성" 버튼 추가 (Sparkles 아이콘)
2. MessageAction 타입에 `{ type: 'generate_proposal'; bidNoticeId: string }` 추가
3. handleAction에서 `generate_proposal` → API 호출 → ContextPanel에 결과 표시

---

### Task 6.2: 제안서 내보내기 (마크다운 + 클립보드)

**Files:**
- Modify: `frontend/kirabot/components/chat/context/ProposalPreview.tsx`

**변경 내용:**
1. ProposalPreview 상단에 [복사] [MD 다운로드] 버튼 추가
2. 복사: `navigator.clipboard.writeText(markdownContent)`
3. MD 다운로드: `Blob` + `URL.createObjectURL` + `<a download>`

---

### Task 6.3: (선택) DOCX 내보내기

**Files:**
- Modify: `services/web_app/main.py` — `/api/proposal/export-docx` 엔드포인트

백엔드에서 마크다운 → DOCX 변환 (python-docx 사용).
프론트에서 `window.open('/api/proposal/export-docx?session_id=xxx')` 호출.

---

## 검증 체크리스트

각 Phase 완료 시:
- [ ] `npm run build` 성공
- [ ] 모든 기존 기능 동작 확인 (검색, 분석, 채팅)
- [ ] 랜딩페이지 변경 없음 (3D 이미지 포함)
- [ ] React Router 네비게이션 동작 (뒤로가기, 딥링크)
- [ ] 사이드바 접힘/펼침 정상 동작
- [ ] 새 색상 시스템 일관성 확인
- [ ] Empty State 표시 확인 (각 페이지)
- [ ] 모바일 반응형 확인 (768px 이하)
