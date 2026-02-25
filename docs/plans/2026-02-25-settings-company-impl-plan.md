# KiraBot 환경설정 + 회사정보 관리 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 사이드바를 3개 내비로 단순화하고, Claude.ai 스타일 통합 설정 페이지를 만들고, 회사 정보를 영구 저장하여 채팅·발주예측에서 자동 활용되게 한다.

**Architecture:** 사이드바 팝오버 + React Router nested routes 설정 페이지 + FastAPI 회사 프로필 CRUD API + OpenAI Structured Outputs로 문서에서 회사 정보 자동 추출 + Resend 이메일 엑셀 발송.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS, Framer Motion, React Router v6, FastAPI, OpenAI, Resend, openpyxl, ChromaDB

---

## Task 1: 사이드바 내비 정리 + 프로필 팝오버

**Files:**
- Modify: `frontend/kirabot/components/chat/Sidebar.tsx`
- Modify: `frontend/kirabot/components/chat/SidebarFooter.tsx`
- Create: `frontend/kirabot/components/sidebar/ProfilePopover.tsx`

**Step 1: Sidebar.tsx — navItems를 3개로 변경**

`frontend/kirabot/components/chat/Sidebar.tsx:17-22` 를 수정:

```typescript
const navItems = [
  { path: '/chat', label: '채팅', icon: MessageSquare },
  { path: '/settings/alerts', label: '알림 설정', icon: Bell },
  { path: '/forecast', label: '발주예측', icon: TrendingUp },
];
```

import에서 `LayoutDashboard` 제거.

**Step 2: ProfilePopover.tsx 생성**

`frontend/kirabot/components/sidebar/ProfilePopover.tsx` 생성:

```tsx
import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, Home, LogOut } from 'lucide-react';

interface ProfilePopoverProps {
  open: boolean;
  onClose: () => void;
  email: string;
  onLogout: () => void;
  onHome: () => void;
}

const ProfilePopover: React.FC<ProfilePopoverProps> = ({ open, onClose, email, onLogout, onHome }) => {
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open, onClose]);

  const items = [
    { label: '설정', icon: Settings, onClick: () => { navigate('/settings'); onClose(); } },
    { label: '홈으로', icon: Home, onClick: () => { onHome(); onClose(); } },
  ];

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.15 }}
          className="absolute bottom-full left-2 right-2 mb-2 rounded-lg bg-gray-800 shadow-xl border border-white/10 overflow-hidden z-50"
        >
          {/* Email */}
          <div className="px-3 py-2.5 text-xs text-slate-400 truncate border-b border-white/10">
            {email}
          </div>

          {/* Menu items */}
          <div className="py-1">
            {items.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={item.onClick}
                  className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-slate-300 hover:bg-gray-700 transition-colors"
                >
                  <Icon size={15} className="shrink-0" />
                  {item.label}
                </button>
              );
            })}
          </div>

          {/* Logout */}
          <div className="border-t border-white/10 py-1">
            <button
              type="button"
              onClick={() => { onLogout(); onClose(); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-red-400 hover:bg-gray-700 transition-colors"
            >
              <LogOut size={15} className="shrink-0" />
              로그아웃
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ProfilePopover;
```

**Step 3: SidebarFooter.tsx — 팝오버 연동으로 교체**

`frontend/kirabot/components/chat/SidebarFooter.tsx` 전체 교체:

```tsx
import React, { useState } from 'react';
import { ChevronUp } from 'lucide-react';
import ProfilePopover from '../sidebar/ProfilePopover';
import type { User } from '../../types';

interface SidebarFooterProps {
  user: User | null;
  collapsed: boolean;
  onLogout: () => void;
  onHome: () => void;
}

const SidebarFooter: React.FC<SidebarFooterProps> = ({ user, collapsed, onLogout, onHome }) => {
  const [popoverOpen, setPopoverOpen] = useState(false);

  if (collapsed) {
    return (
      <div className="relative border-t border-white/10 p-2">
        <button
          type="button"
          onClick={() => setPopoverOpen(!popoverOpen)}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
          title={user?.name || '사용자'}
        >
          {user?.avatarUrl ? (
            <img src={user.avatarUrl} alt="" className="h-7 w-7 rounded-full" />
          ) : (
            <span className="text-xs">{user?.name?.charAt(0) || '?'}</span>
          )}
        </button>
        <ProfilePopover
          open={popoverOpen}
          onClose={() => setPopoverOpen(false)}
          email={user?.email || ''}
          onLogout={onLogout}
          onHome={onHome}
        />
      </div>
    );
  }

  return (
    <div className="relative border-t border-white/10 p-3">
      <button
        type="button"
        onClick={() => setPopoverOpen(!popoverOpen)}
        className="flex w-full items-center gap-2 rounded-lg px-1 py-1.5 hover:bg-sidebar-hover transition-colors"
      >
        {user?.avatarUrl ? (
          <img src={user.avatarUrl} alt="" className="h-8 w-8 rounded-full shrink-0" />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-hover text-xs text-white shrink-0">
            {user?.name?.charAt(0) || '?'}
          </div>
        )}
        <div className="min-w-0 flex-1 text-left">
          <p className="truncate text-sm font-medium text-white">{user?.name || '사용자'}</p>
          <p className="truncate text-xs text-slate-400">{user?.email || ''}</p>
        </div>
        <ChevronUp size={14} className={`text-slate-400 transition-transform shrink-0 ${popoverOpen ? '' : 'rotate-180'}`} />
      </button>
      <ProfilePopover
        open={popoverOpen}
        onClose={() => setPopoverOpen(false)}
        email={user?.email || ''}
        onLogout={onLogout}
        onHome={onHome}
      />
    </div>
  );
};

export default SidebarFooter;
```

**Step 4: 빌드 확인**

```bash
cd frontend/kirabot && npm run build
```
Expected: 빌드 성공 (DashboardPage import는 아직 App.tsx에 유지)

**Step 5: 커밋**

```bash
git add frontend/kirabot/components/chat/Sidebar.tsx frontend/kirabot/components/chat/SidebarFooter.tsx frontend/kirabot/components/sidebar/ProfilePopover.tsx
git commit -m "feat: simplify sidebar nav to 3 items + add profile popover menu"
```

---

## Task 2: 설정 페이지 레이아웃 + 라우팅

**Files:**
- Create: `frontend/kirabot/components/settings/SettingsPage.tsx`
- Modify: `frontend/kirabot/App.tsx`
- Modify: `frontend/kirabot/components/layout/AppShell.tsx`

**Step 1: SettingsPage.tsx 생성 (좌측탭 + Outlet)**

```tsx
import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, User as UserIcon, Building2, BarChart3, Shield } from 'lucide-react';
import { pageTransition } from '../../utils/animations';

const tabs = [
  { path: 'general', label: '일반', icon: UserIcon },
  { path: 'company', label: '회사 정보', icon: Building2 },
  { path: 'usage', label: '사용량', icon: BarChart3 },
  { path: 'account', label: '계정', icon: Shield },
];

const SettingsPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <motion.div
      className="flex-1 flex flex-col h-full bg-white overflow-hidden"
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-200">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft size={16} />
          설정
        </button>
      </div>

      {/* Body: left tabs + right content */}
      <div className="flex flex-1 min-h-0">
        {/* Left tab nav */}
        <nav className="w-48 shrink-0 border-r border-slate-200 py-4 px-3 space-y-0.5">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <NavLink
                key={tab.path}
                to={tab.path}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? 'bg-kira-50 text-kira-700 font-semibold border-l-2 border-kira-500 -ml-px'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                <Icon size={16} className="shrink-0" />
                {tab.label}
              </NavLink>
            );
          })}
        </nav>

        {/* Right content */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div className="max-w-2xl mx-auto">
            <Outlet />
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default SettingsPage;
```

**Step 2: App.tsx에 설정 라우트 추가**

`frontend/kirabot/App.tsx` 수정:

import 추가 (line 1 근처):
```typescript
import SettingsPage from './components/settings/SettingsPage';
```

protected routes 블록 (line 169-181) 을 교체:

```tsx
{/* Protected app routes */}
<Route element={
  <ProtectedRoute user={user}>
    <ChatProvider>
      <AppShell user={user} onLogout={() => void handleLogout()} />
    </ChatProvider>
  </ProtectedRoute>
}>
  <Route path="/chat" element={<ChatPage user={user} />} />
  <Route path="/settings/alerts" element={<AlertSettingsPage />} />
  <Route path="/forecast" element={<ForecastPage />} />

  {/* Settings nested routes */}
  <Route path="/settings" element={<SettingsPage />}>
    <Route index element={<Navigate to="general" replace />} />
    <Route path="general" element={<SettingsGeneralPlaceholder />} />
    <Route path="company" element={<SettingsCompanyPlaceholder />} />
    <Route path="usage" element={<DashboardPage />} />
    <Route path="account" element={<SettingsAccountPlaceholder />} />
  </Route>

  {/* Legacy redirect */}
  <Route path="/dashboard" element={<Navigate to="/settings/usage" replace />} />
</Route>
```

임시 플레이스홀더 함수들을 App.tsx 안에 추가 (AppRoutes 위):
```tsx
function SettingsGeneralPlaceholder() {
  return <div className="text-slate-500 text-sm">일반 설정 (준비 중)</div>;
}
function SettingsCompanyPlaceholder() {
  return <div className="text-slate-500 text-sm">회사 정보 (준비 중)</div>;
}
function SettingsAccountPlaceholder() {
  return <div className="text-slate-500 text-sm">계정 설정 (준비 중)</div>;
}
```

**Step 3: AppShell.tsx — /settings 경로에서 사이드바 숨김**

`frontend/kirabot/components/layout/AppShell.tsx` 수정:

```tsx
import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import Sidebar from '../chat/Sidebar';
import type { User } from '../../types';

interface AppShellProps {
  user: User | null;
  onLogout: () => void;
}

const AppShell: React.FC<AppShellProps> = ({ user, onLogout }) => {
  const navigate = useNavigate();
  const location = useLocation();
  // /settings (but NOT /settings/alerts) → hide sidebar
  const isSettingsPage = location.pathname.startsWith('/settings') && !location.pathname.startsWith('/settings/alerts');

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {!isSettingsPage && (
        <Sidebar user={user} onLogout={onLogout} onHome={() => navigate('/')} />
      )}
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
};

export default AppShell;
```

**Step 4: 빌드 확인**

```bash
cd frontend/kirabot && npm run build
```

**Step 5: 커밋**

```bash
git add frontend/kirabot/components/settings/SettingsPage.tsx frontend/kirabot/App.tsx frontend/kirabot/components/layout/AppShell.tsx
git commit -m "feat: add settings page layout with nested routes + sidebar hiding"
```

---

## Task 3: SettingsGeneral + SettingsAccount

**Files:**
- Create: `frontend/kirabot/components/settings/SettingsGeneral.tsx`
- Create: `frontend/kirabot/components/settings/SettingsAccount.tsx`
- Modify: `frontend/kirabot/App.tsx` (플레이스홀더 → 실제 컴포넌트)

**Step 1: SettingsGeneral.tsx**

```tsx
import React from 'react';

interface SettingsGeneralProps {
  user?: { name: string; email: string; avatarUrl?: string } | null;
}

const SettingsGeneral: React.FC<SettingsGeneralProps> = ({ user }) => {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">프로필</h2>
        <div className="flex items-center gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
          {user?.avatarUrl ? (
            <img src={user.avatarUrl} alt="" className="h-14 w-14 rounded-full" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-kira-100 text-lg font-bold text-kira-600">
              {user?.name?.charAt(0) || '?'}
            </div>
          )}
          <div>
            <p className="text-base font-medium text-slate-900">{user?.name || '사용자'}</p>
            <p className="text-sm text-slate-500">{user?.email || ''}</p>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">모양</h2>
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-sm font-medium text-slate-700 mb-3">테마</p>
          <div className="flex gap-3">
            {(['시스템', '라이트', '다크'] as const).map((label) => (
              <label key={label} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="theme"
                  value={label}
                  defaultChecked={label === '라이트'}
                  className="text-kira-600 focus:ring-kira-500"
                />
                <span className="text-sm text-slate-700">{label}</span>
              </label>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-2">테마 기능은 추후 지원 예정입니다.</p>
        </div>
      </div>
    </div>
  );
};

export default SettingsGeneral;
```

**Step 2: SettingsAccount.tsx**

```tsx
import React, { useState } from 'react';

interface SettingsAccountProps {
  user?: { email: string } | null;
  onLogout: () => void;
}

const SettingsAccount: React.FC<SettingsAccountProps> = ({ user, onLogout }) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">로그인 정보</h2>
        <div className="rounded-xl border border-slate-200 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">Google 계정</p>
              <p className="text-sm text-slate-500">{user?.email || '-'}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onLogout}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            로그아웃
          </button>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-red-600 mb-4">위험 구역</h2>
        <div className="rounded-xl border border-red-200 p-4">
          {!showDeleteConfirm ? (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="text-sm text-red-600 hover:text-red-700 font-medium"
            >
              계정 삭제
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-slate-700">정말로 계정을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                >
                  취소
                </button>
                <button
                  type="button"
                  onClick={onLogout}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
                >
                  삭제 확인
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsAccount;
```

**Step 3: App.tsx — 플레이스홀더를 실제 컴포넌트로 교체**

import 추가:
```typescript
import SettingsGeneral from './components/settings/SettingsGeneral';
import SettingsAccount from './components/settings/SettingsAccount';
```

라우트에서 플레이스홀더 교체 + user/onLogout prop 전달.
SettingsPage에 user와 onLogout을 전달하려면 **wrapper 패턴** 사용:

```tsx
<Route path="/settings" element={<SettingsPage />}>
  <Route index element={<Navigate to="general" replace />} />
  <Route path="general" element={<SettingsGeneral user={user} />} />
  <Route path="company" element={<SettingsCompanyPlaceholder />} />
  <Route path="usage" element={<DashboardPage />} />
  <Route path="account" element={<SettingsAccount user={user} onLogout={() => void handleLogout()} />} />
</Route>
```

플레이스홀더 함수 2개 제거 (SettingsGeneralPlaceholder, SettingsAccountPlaceholder). SettingsCompanyPlaceholder만 유지.

**Step 4: 빌드 확인**

```bash
cd frontend/kirabot && npm run build
```

**Step 5: 커밋**

```bash
git add frontend/kirabot/components/settings/SettingsGeneral.tsx frontend/kirabot/components/settings/SettingsAccount.tsx frontend/kirabot/App.tsx
git commit -m "feat: add general + account settings tabs"
```

---

## Task 4: 백엔드 — 회사 프로필 CRUD API

**Files:**
- Modify: `services/web_app/main.py` (엔드포인트 추가)
- 저장소: `data/company_profiles/{username}/`

**Step 1: 인증 헬퍼 함수 추가**

`services/web_app/main.py`에 `_require_username` 헬퍼 추가 (기존 `_resolve_usage_actor` 근처):

```python
def _require_username(request: Request) -> str:
    """쿠키에서 username 추출. 미인증 시 401."""
    token = str(request.cookies.get(_auth_cookie_name(), "") or "")
    username = str(resolve_user_from_session(token) or "")
    if not username:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return username
```

**Step 2: 프로필 저장/로드 유틸**

```python
import json
import shutil
import uuid
from pathlib import Path

_COMPANY_PROFILES_DIR = ROOT_DIR / "data" / "company_profiles"

def _company_profile_dir(username: str) -> Path:
    safe = username.replace("/", "_").replace("..", "_")
    return _COMPANY_PROFILES_DIR / safe

def _load_company_profile(username: str) -> dict | None:
    path = _company_profile_dir(username) / "profile.json"
    if not path.exists():
        return None
    return json.loads(path.read_text("utf-8"))

def _save_company_profile(username: str, profile: dict) -> None:
    dirp = _company_profile_dir(username)
    dirp.mkdir(parents=True, exist_ok=True)
    profile["updatedAt"] = datetime.now(timezone.utc).isoformat()
    (dirp / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), "utf-8")
```

**Step 3: GET /api/company/profile**

```python
@app.get("/api/company/profile")
def get_company_profile(request: Request) -> dict[str, Any]:
    username = _require_username(request)
    profile = _load_company_profile(username)
    if not profile:
        return {"ok": True, "profile": None}
    return {"ok": True, "profile": profile}
```

**Step 4: POST /api/company/profile (문서 업로드 + LLM 추출)**

```python
@app.post("/api/company/profile")
async def upload_company_profile_docs(
    request: Request,
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    username = _require_username(request)
    dirp = _company_profile_dir(username)
    docs_dir = dirp / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    profile = _load_company_profile(username) or {
        "companyName": "",
        "businessType": "",
        "businessNumber": "",
        "certifications": [],
        "regions": [],
        "employeeCount": None,
        "annualRevenue": "",
        "keyExperience": [],
        "specializations": [],
        "documents": [],
        "aiExtraction": None,
        "lastAnalyzedAt": None,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }

    MAX_SIZE = 10 * 1024 * 1024  # 10MB (무료)
    allowed_ext = {".pdf", ".doc", ".docx", ".txt", ".md", ".hwp", ".hwpx", ".xlsx", ".xls", ".csv", ".pptx", ".ppt"}
    saved_docs = []
    all_text = ""

    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in allowed_ext:
            raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식: {ext}")
        content = await f.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=400, detail=f"파일 크기 초과 (최대 10MB): {f.filename}")

        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        safe_name = f.filename or "document"
        save_path = docs_dir / f"{doc_id}_{safe_name}"
        save_path.write_bytes(content)

        saved_docs.append({
            "id": doc_id,
            "name": safe_name,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "size": len(content),
        })

        # Extract text using existing document_parser
        try:
            from document_parser import extract_text_from_file
            text = extract_text_from_file(str(save_path))
            all_text += f"\n--- {safe_name} ---\n{text[:8000]}\n"
        except Exception:
            pass

    profile["documents"] = profile.get("documents", []) + saved_docs

    # LLM extraction
    if all_text.strip():
        try:
            extraction = await _extract_company_info_llm(all_text)
            profile["aiExtraction"] = {
                "summary": extraction.get("summary", ""),
                "extractedAt": datetime.now(timezone.utc).isoformat(),
                "raw": extraction,
            }
            profile["lastAnalyzedAt"] = datetime.now(timezone.utc).isoformat()
            # Auto-fill empty fields
            for key in ("companyName", "businessType", "businessNumber", "annualRevenue"):
                if not profile.get(key) and extraction.get(key):
                    profile[key] = extraction[key]
            for key in ("certifications", "regions", "keyExperience", "specializations"):
                existing = set(profile.get(key, []))
                for v in extraction.get(key, []):
                    existing.add(v)
                profile[key] = list(existing)
            if not profile.get("employeeCount") and extraction.get("employeeCount"):
                profile["employeeCount"] = extraction["employeeCount"]
        except Exception as e:
            logger.warning("Company profile LLM extraction failed: %s", e)

    _save_company_profile(username, profile)

    # Also add to permanent vector DB for RAG
    try:
        _add_company_docs_to_vectordb(username, all_text)
    except Exception as e:
        logger.warning("Company vectordb update failed: %s", e)

    return {"ok": True, "profile": profile}
```

**Step 5: LLM 추출 함수**

```python
async def _extract_company_info_llm(text: str) -> dict:
    """OpenAI를 사용하여 문서에서 회사 정보 추출."""
    import openai
    client = openai.OpenAI()

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": (
                "다음 문서에서 회사 정보를 추출하세요. JSON으로 반환하세요.\n"
                "필드: companyName, businessType, businessNumber, certifications(배열), "
                "regions(배열), employeeCount(숫자), annualRevenue(문자열), "
                "keyExperience(배열), specializations(배열), summary(한줄 요약)"
            )},
            {"role": "user", "content": text[:12000]},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content or "{}")
```

**Step 6: PUT /api/company/profile (수동 편집)**

```python
@app.put("/api/company/profile")
async def update_company_profile(request: Request) -> dict[str, Any]:
    username = _require_username(request)
    body = await request.json()
    profile = _load_company_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail="회사 프로필이 없습니다.")

    editable = ("companyName", "businessType", "businessNumber", "certifications",
                "regions", "employeeCount", "annualRevenue", "keyExperience", "specializations")
    for key in editable:
        if key in body:
            profile[key] = body[key]

    _save_company_profile(username, profile)
    return {"ok": True, "profile": profile}
```

**Step 7: DELETE 엔드포인트들**

```python
@app.delete("/api/company/profile")
def delete_company_profile(request: Request) -> dict[str, Any]:
    username = _require_username(request)
    dirp = _company_profile_dir(username)
    if dirp.exists():
        shutil.rmtree(dirp, ignore_errors=True)
    return {"ok": True}

@app.delete("/api/company/documents/{doc_id}")
def delete_company_document(request: Request, doc_id: str) -> dict[str, Any]:
    username = _require_username(request)
    profile = _load_company_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail="프로필 없음")

    profile["documents"] = [d for d in profile.get("documents", []) if d["id"] != doc_id]

    # Delete actual file
    docs_dir = _company_profile_dir(username) / "documents"
    for f in docs_dir.glob(f"{doc_id}_*"):
        f.unlink(missing_ok=True)

    _save_company_profile(username, profile)
    return {"ok": True, "profile": profile}

@app.post("/api/company/reanalyze")
async def reanalyze_company_profile(request: Request) -> dict[str, Any]:
    username = _require_username(request)
    profile = _load_company_profile(username)
    if not profile or not profile.get("documents"):
        raise HTTPException(status_code=400, detail="등록된 문서가 없습니다.")

    docs_dir = _company_profile_dir(username) / "documents"
    all_text = ""
    for doc in profile["documents"]:
        for f in docs_dir.glob(f"{doc['id']}_*"):
            try:
                from document_parser import extract_text_from_file
                text = extract_text_from_file(str(f))
                all_text += f"\n--- {doc['name']} ---\n{text[:8000]}\n"
            except Exception:
                pass

    if not all_text.strip():
        raise HTTPException(status_code=400, detail="문서에서 텍스트를 추출할 수 없습니다.")

    extraction = await _extract_company_info_llm(all_text)
    profile["aiExtraction"] = {
        "summary": extraction.get("summary", ""),
        "extractedAt": datetime.now(timezone.utc).isoformat(),
        "raw": extraction,
    }
    profile["lastAnalyzedAt"] = datetime.now(timezone.utc).isoformat()
    _save_company_profile(username, profile)
    return {"ok": True, "profile": profile}
```

**Step 8: 벡터DB 영구 저장 헬퍼**

```python
def _add_company_docs_to_vectordb(username: str, text: str) -> None:
    """유저별 영구 벡터 컬렉션에 회사 문서 추가."""
    if not text.strip():
        return
    from engine import RAGEngine
    safe = username.replace("/", "_").replace("..", "_")
    collection_name = f"company_{safe}"
    engine = RAGEngine(
        persist_dir=str(ROOT_DIR / "data" / "vectordb"),
        collection_name=collection_name,
    )
    # Split text into chunks and add
    chunks = [text[i:i+1000] for i in range(0, len(text), 800)]
    engine.add_texts(chunks[:50])  # Cap at 50 chunks
```

**Step 9: 서버 재시작 + 테스트**

```bash
# 서버 재시작
kill $(lsof -ti:8000) && sleep 2 && python services/web_app/main.py &

# GET (빈 프로필)
curl -s http://localhost:8000/api/company/profile -b "kira_auth=<token>"

# POST (문서 업로드)
curl -s -X POST http://localhost:8000/api/company/profile \
  -b "kira_auth=<token>" \
  -F "files=@docs/dummy/sample.pdf"
```

**Step 10: 커밋**

```bash
git add services/web_app/main.py
git commit -m "feat: add company profile CRUD API with LLM extraction"
```

---

## Task 5: 프론트엔드 — kiraApiService에 회사 프로필 API 추가

**Files:**
- Modify: `frontend/kirabot/services/kiraApiService.ts`
- Modify: `frontend/kirabot/types.ts`

**Step 1: types.ts에 CompanyProfile 타입 추가**

```typescript
export interface CompanyDocument {
  id: string;
  name: string;
  uploadedAt: string;
  size: number;
}

export interface AiExtraction {
  summary: string;
  extractedAt: string;
  raw: Record<string, unknown>;
}

export interface CompanyProfile {
  companyName: string;
  businessType: string;
  businessNumber: string;
  certifications: string[];
  regions: string[];
  employeeCount: number | null;
  annualRevenue: string;
  keyExperience: string[];
  specializations: string[];
  documents: CompanyDocument[];
  aiExtraction: AiExtraction | null;
  lastAnalyzedAt: string | null;
  createdAt: string;
  updatedAt?: string;
}
```

**Step 2: kiraApiService.ts에 API 함수 추가**

```typescript
// ── 회사 프로필 API ──

export async function getCompanyProfile(): Promise<CompanyProfile | null> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'GET',
    credentials: 'include',
  });
  const data = await parseJson<{ profile: CompanyProfile | null }>(res);
  return data.profile;
}

export async function uploadCompanyProfileDocs(files: File[]): Promise<CompanyProfile> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const res = await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'POST',
    credentials: 'include',
    body: form,
    timeoutMs: 180_000,
  });
  const data = await parseJson<{ profile: CompanyProfile }>(res);
  return data.profile;
}

export async function updateCompanyProfile(updates: Partial<CompanyProfile>): Promise<CompanyProfile> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  const data = await parseJson<{ profile: CompanyProfile }>(res);
  return data.profile;
}

export async function deleteCompanyProfile(): Promise<void> {
  await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'DELETE',
    credentials: 'include',
  });
}

export async function deleteCompanyDocument(docId: string): Promise<CompanyProfile> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company/documents/${docId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  const data = await parseJson<{ profile: CompanyProfile }>(res);
  return data.profile;
}

export async function reanalyzeCompanyProfile(): Promise<CompanyProfile> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company/reanalyze`, {
    method: 'POST',
    credentials: 'include',
    timeoutMs: 180_000,
  });
  const data = await parseJson<{ profile: CompanyProfile }>(res);
  return data.profile;
}
```

**Step 3: 빌드 확인**

```bash
cd frontend/kirabot && npm run build
```

**Step 4: 커밋**

```bash
git add frontend/kirabot/services/kiraApiService.ts frontend/kirabot/types.ts
git commit -m "feat: add company profile API client functions"
```

---

## Task 6: SettingsCompany UI

**Files:**
- Create: `frontend/kirabot/components/settings/SettingsCompany.tsx`
- Modify: `frontend/kirabot/App.tsx` (플레이스홀더 → 실제 컴포넌트)

**Step 1: SettingsCompany.tsx 생성**

```tsx
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Upload, Trash2, RefreshCw, Sparkles, FileText } from 'lucide-react';
import ChipInput from '../shared/ChipInput';
import {
  getCompanyProfile,
  uploadCompanyProfileDocs,
  updateCompanyProfile,
  deleteCompanyDocument,
  reanalyzeCompanyProfile,
  type CompanyProfile,
} from '../../services/kiraApiService';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

const SettingsCompany: React.FC = () => {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Form state
  const [companyName, setCompanyName] = useState('');
  const [businessType, setBusinessType] = useState('');
  const [businessNumber, setBusinessNumber] = useState('');
  const [certifications, setCertifications] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [employeeCount, setEmployeeCount] = useState('');
  const [annualRevenue, setAnnualRevenue] = useState('');
  const [keyExperience, setKeyExperience] = useState<string[]>([]);
  const [specializations, setSpecializations] = useState<string[]>([]);

  const fillForm = useCallback((p: CompanyProfile) => {
    setCompanyName(p.companyName || '');
    setBusinessType(p.businessType || '');
    setBusinessNumber(p.businessNumber || '');
    setCertifications(p.certifications || []);
    setRegions(p.regions || []);
    setEmployeeCount(p.employeeCount ? String(p.employeeCount) : '');
    setAnnualRevenue(p.annualRevenue || '');
    setKeyExperience(p.keyExperience || []);
    setSpecializations(p.specializations || []);
  }, []);

  useEffect(() => {
    getCompanyProfile()
      .then((p) => {
        setProfile(p);
        if (p) fillForm(p);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [fillForm]);

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const updated = await updateCompanyProfile({
        companyName, businessType, businessNumber,
        certifications, regions, specializations, keyExperience,
        employeeCount: employeeCount ? parseInt(employeeCount) : null,
        annualRevenue,
      });
      setProfile(updated);
      setSaveMsg('저장되었습니다.');
      setTimeout(() => setSaveMsg(''), 3000);
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (fileList: FileList) => {
    setUploading(true);
    try {
      const files = Array.from(fileList);
      const updated = await uploadCompanyProfileDocs(files);
      setProfile(updated);
      fillForm(updated);
    } catch (e) {
      alert(e instanceof Error ? e.message : '업로드 실패');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      const updated = await deleteCompanyDocument(docId);
      setProfile(updated);
    } catch { /* ignore */ }
  };

  const handleReanalyze = async () => {
    setReanalyzing(true);
    try {
      const updated = await reanalyzeCompanyProfile();
      setProfile(updated);
    } catch (e) {
      alert(e instanceof Error ? e.message : '재분석 실패');
    } finally {
      setReanalyzing(false);
    }
  };

  const handleApplyAi = () => {
    if (!profile?.aiExtraction?.raw) return;
    const raw = profile.aiExtraction.raw as Record<string, unknown>;
    if (raw.companyName) setCompanyName(String(raw.companyName));
    if (raw.businessType) setBusinessType(String(raw.businessType));
    if (raw.businessNumber) setBusinessNumber(String(raw.businessNumber));
    if (Array.isArray(raw.certifications)) setCertifications(raw.certifications as string[]);
    if (Array.isArray(raw.regions)) setRegions(raw.regions as string[]);
    if (raw.employeeCount) setEmployeeCount(String(raw.employeeCount));
    if (raw.annualRevenue) setAnnualRevenue(String(raw.annualRevenue));
    if (Array.isArray(raw.keyExperience)) setKeyExperience(raw.keyExperience as string[]);
    if (Array.isArray(raw.specializations)) setSpecializations(raw.specializations as string[]);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="flex gap-1">
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-1">회사 정보 관리</h2>
        <p className="text-sm text-slate-500 mb-6">
          회사 정보를 등록하면 입찰 분석, 발주예측, 알림 설정에서 자동으로 활용됩니다.
        </p>
      </div>

      {/* 프로필 폼 */}
      <div className="rounded-xl border border-slate-200 p-5 space-y-4">
        <h3 className="text-base font-semibold text-slate-800">회사 프로필</h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">회사명</label>
            <input value={companyName} onChange={e => setCompanyName(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">업종</label>
            <input value={businessType} onChange={e => setBusinessType(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">사업자번호</label>
            <input value={businessNumber} onChange={e => setBusinessNumber(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">연매출</label>
            <input value={annualRevenue} onChange={e => setAnnualRevenue(e.target.value)} placeholder="예: 30억" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">직원 수</label>
            <input type="number" value={employeeCount} onChange={e => setEmployeeCount(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">자격증/인증</label>
          <ChipInput values={certifications} onChange={setCertifications} placeholder="자격증 입력 후 Enter" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">활동 지역</label>
          <ChipInput values={regions} onChange={setRegions} placeholder="지역 입력 후 Enter" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">전문 분야</label>
          <ChipInput values={specializations} onChange={setSpecializations} placeholder="전문 분야 입력 후 Enter" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">주요 경험</label>
          <ChipInput values={keyExperience} onChange={setKeyExperience} placeholder="주요 경험 입력 후 Enter" />
        </div>

        <div className="flex items-center gap-3">
          <button type="button" onClick={handleSave} disabled={saving}
            className="rounded-lg bg-kira-600 px-5 py-2 text-sm font-medium text-white hover:bg-kira-700 disabled:opacity-50 transition-colors">
            {saving ? '저장 중...' : '프로필 저장'}
          </button>
          {saveMsg && <span className="text-sm text-emerald-600">{saveMsg}</span>}
        </div>
      </div>

      {/* 문서 목록 + 업로드 */}
      <div className="rounded-xl border border-slate-200 p-5 space-y-4">
        <h3 className="text-base font-semibold text-slate-800">등록 문서</h3>

        {profile?.documents && profile.documents.length > 0 && (
          <div className="space-y-2">
            {profile.documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText size={16} className="text-slate-400 shrink-0" />
                  <span className="text-sm text-slate-700 truncate">{doc.name}</span>
                  <span className="text-xs text-slate-400 shrink-0">{formatBytes(doc.size)}</span>
                </div>
                <button type="button" onClick={() => handleDeleteDoc(doc.id)}
                  className="text-slate-400 hover:text-red-500 transition-colors shrink-0">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 업로드 영역 */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onDrop={(e) => { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files); }}
          className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 hover:border-kira-400 py-8 cursor-pointer transition-colors"
        >
          {uploading ? (
            <div className="flex gap-1">
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
            </div>
          ) : (
            <>
              <Upload size={24} className="text-slate-400 mb-2" />
              <p className="text-sm text-slate-600 font-medium">파일을 드래그하거나 클릭하여 업로드</p>
              <p className="text-xs text-slate-400 mt-1">PDF, DOCX, HWP, TXT, MD, PPT (최대 10MB)</p>
            </>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx,.txt,.md,.hwp,.hwpx,.xlsx,.xls,.csv,.pptx,.ppt"
          onChange={(e) => { if (e.target.files?.length) handleUpload(e.target.files); e.target.value = ''; }}
          className="hidden"
        />
      </div>

      {/* AI 추출 요약 */}
      {profile?.aiExtraction && (
        <div className="rounded-xl border border-kira-200 bg-kira-50/50 p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-kira-600" />
            <h3 className="text-base font-semibold text-slate-800">AI 추출 역량 요약</h3>
          </div>
          <p className="text-sm text-slate-700">{profile.aiExtraction.summary || '요약 정보가 없습니다.'}</p>
          <div className="flex gap-2">
            <button type="button" onClick={handleReanalyze} disabled={reanalyzing}
              className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50">
              <RefreshCw size={14} className={reanalyzing ? 'animate-spin' : ''} />
              재분석
            </button>
            <button type="button" onClick={handleApplyAi}
              className="flex items-center gap-1.5 rounded-lg bg-kira-600 px-3 py-1.5 text-sm text-white hover:bg-kira-700">
              <Sparkles size={14} />
              프로필에 반영
            </button>
          </div>
        </div>
      )}

      {/* 미등록 안내 */}
      {!profile && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center">
          <Upload size={32} className="text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500">회사 문서를 업로드하면 AI가 자동으로 정보를 추출합니다.</p>
        </div>
      )}
    </div>
  );
};

export default SettingsCompany;
```

**Step 2: App.tsx — SettingsCompanyPlaceholder → SettingsCompany 교체**

import 추가:
```typescript
import SettingsCompany from './components/settings/SettingsCompany';
```

라우트에서 `<SettingsCompanyPlaceholder />` → `<SettingsCompany />` 교체. SettingsCompanyPlaceholder 함수 삭제.

**Step 3: 빌드 확인**

```bash
cd frontend/kirabot && npm run build
```

**Step 4: 커밋**

```bash
git add frontend/kirabot/components/settings/SettingsCompany.tsx frontend/kirabot/App.tsx
git commit -m "feat: add company info settings page with upload + AI extraction"
```

---

## Task 7: 알림 이메일 엑셀 발송

**Files:**
- Modify: `services/web_app/main.py`
- Modify: `requirements.txt`

**Step 1: requirements.txt에 패키지 추가**

```
resend
openpyxl
```

**Step 2: 엑셀 생성 함수**

`services/web_app/main.py`에 추가:

```python
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

def _build_alert_excel(bids: list[dict]) -> bytes:
    """알림 공고 목록을 엑셀 바이트로 생성."""
    wb = Workbook()
    ws = wb.active
    ws.title = "공고 알림"

    headers = ["구분", "공고명", "수요처", "부서", "예산금액",
               "공고 게시일시", "입찰서 제출일시", "입찰서 마감일시", "낙찰방법", "비고"]

    # Header styling
    header_font = Font(bold=True, size=10)
    header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, bid in enumerate(bids, 2):
        values = [
            bid.get("category", ""),
            bid.get("title", ""),
            bid.get("demandOrg", bid.get("issuingOrg", "")),
            bid.get("department", ""),
            bid.get("estimatedPrice", ""),
            bid.get("publishedAt", ""),
            bid.get("submitStartAt", ""),
            bid.get("deadlineAt", ""),
            bid.get("awardMethod", ""),
            bid.get("remarks", ""),
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center")

    # Auto-width
    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

**Step 3: 이메일 발송 함수**

```python
def _send_alert_email(to_email: str, subject: str, bids: list[dict]) -> bool:
    """Resend API로 엑셀 첨부 이메일 발송."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "noreply@kirabot.co.kr").strip()
    if not api_key:
        logger.warning("RESEND_API_KEY not set, skipping email")
        return False

    import resend
    resend.api_key = api_key

    excel_bytes = _build_alert_excel(bids)
    today = datetime.now().strftime("%Y%m%d")

    try:
        resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "text": f"키라봇 공고 알림입니다. {len(bids)}건의 매칭 공고를 첨부 엑셀에서 확인해주세요.",
            "attachments": [{
                "filename": f"kirabot_alert_{today}.xlsx",
                "content": list(excel_bytes),
            }],
        })
        return True
    except Exception as e:
        logger.error("Alert email send failed: %s", e)
        return False
```

**Step 4: 수동 알림 발송 엔드포인트**

```python
@app.post("/api/alerts/send-now")
async def send_alert_now(request: Request) -> dict[str, Any]:
    """알림 설정 기반으로 즉시 공고 검색 + 이메일 발송."""
    body = await request.json()
    session_id = body.get("session_id", "")

    # Load alert config
    config_path = ROOT_DIR / "data" / "alert_configs" / f"{_sanitize_session_id(session_id)}.json"
    if not config_path.exists():
        raise HTTPException(status_code=400, detail="알림 설정이 없습니다.")
    config = json.loads(config_path.read_text("utf-8"))

    if not config.get("email"):
        raise HTTPException(status_code=400, detail="수신 이메일이 설정되지 않았습니다.")

    # Search bids for each rule
    all_bids = []
    for rule in config.get("rules", []):
        if not rule.get("enabled", True):
            continue
        try:
            from services.web_app.nara_api import search_bids
            results = await search_bids(
                keywords=rule.get("keywords", []),
                categories=rule.get("categories", []),
                regions=rule.get("regions", []),
                date_from=(datetime.now() - timedelta(days=7)).strftime("%Y%m%d"),
                date_to=datetime.now().strftime("%Y%m%d"),
                page_size=50,
            )
            all_bids.extend(results.get("items", []))
        except Exception as e:
            logger.warning("Alert search failed for rule: %s", e)

    if not all_bids:
        return {"ok": True, "sent": False, "reason": "매칭 공고가 없습니다.", "count": 0}

    # Deduplicate by bid ID
    seen = set()
    unique = []
    for b in all_bids:
        bid_id = b.get("id", b.get("bidNtceNo", ""))
        if bid_id not in seen:
            seen.add(bid_id)
            unique.append(b)

    sent = _send_alert_email(
        config["email"],
        f"[키라봇] 맞춤 공고 알림 ({len(unique)}건)",
        unique,
    )
    return {"ok": True, "sent": sent, "count": len(unique)}
```

**Step 5: 빌드/테스트**

```bash
pip install resend openpyxl
# 서버 재시작 후 테스트
```

**Step 6: 커밋**

```bash
git add services/web_app/main.py requirements.txt
git commit -m "feat: add alert email with Excel attachment via Resend"
```

---

## Task 8: 채팅 연동 — 회사 프로필 자동 활용

**Files:**
- Modify: `frontend/kirabot/hooks/useConversationFlow.ts`
- Modify: `frontend/kirabot/components/chat/ChatHeader.tsx`

**Step 1: useConversationFlow.ts — 세션 시작 시 프로필 확인**

`useConversationFlow.ts` 상단 import에 추가:
```typescript
import { getCompanyProfile } from '../services/kiraApiService';
```

`startNewConversation` 함수에서 greeting 메시지 push 후, 프로필 확인 로직 추가:

```typescript
// greeting 메시지 push 직후에 추가
getCompanyProfile().then((profile) => {
  if (profile && profile.companyName) {
    updateConv({ companyProfile: profile });
    pushText(`🏢 ${profile.companyName} 정보가 연동되었습니다. 입찰 분석 시 자동으로 활용됩니다.`);
  }
}).catch(() => {});
```

**Step 2: 회사 문서 등록 단계 스킵 로직**

`handleAction`에서 `welcome_action` → `start_doc_analysis` 분기에서:

```typescript
// 기존: "회사 문서 먼저 등록" / "바로 문서 분석" 선택지 push
// 변경: companyProfile이 있으면 바로 doc_upload_target으로 스킵

if (conversation.companyProfile) {
  // 회사 정보 이미 있음 → 바로 분석 문서 업로드
  setPhase('doc_upload_target');
  push({ /* file_upload message for target doc */ });
} else {
  // 기존 플로우: 선택지 제공
  push({ /* button_choice: 회사 문서 먼저 등록 / 바로 문서 분석 */ });
}
```

**Step 3: ChatHeader.tsx — 회사 연동 뱃지**

ChatHeader에 뱃지 추가:

```tsx
{conversation?.companyProfile?.companyName && (
  <span className="flex items-center gap-1 rounded-full bg-kira-50 border border-kira-200 px-2.5 py-0.5 text-xs text-kira-700">
    🏢 {conversation.companyProfile.companyName}
  </span>
)}
```

**Step 4: Conversation 타입에 companyProfile 추가**

`frontend/kirabot/types.ts`의 Conversation 인터페이스에:

```typescript
companyProfile?: CompanyProfile | null;
```

**Step 5: 프로필 없을 때 안내 메시지**

`useConversationFlow.ts`에서 프로필 없으면:
```typescript
pushText('💡 설정 > 회사 정보에서 등록하면 매번 업로드 없이 자동 분석됩니다.');
```

**Step 6: 빌드 + 커밋**

```bash
cd frontend/kirabot && npm run build
git add frontend/kirabot/hooks/useConversationFlow.ts frontend/kirabot/components/chat/ChatHeader.tsx frontend/kirabot/types.ts
git commit -m "feat: auto-use company profile in chat flow"
```

---

## Task 9: 발주예측 연동 — 맞춤 추천

**Files:**
- Modify: `frontend/kirabot/components/forecast/ForecastPage.tsx`
- Modify: `services/web_app/main.py`

**Step 1: ForecastPage.tsx — 회사 프로필 로드 + 맞춤 추천 섹션**

ForecastPage 상단에 프로필 로드:

```typescript
import { getCompanyProfile, type CompanyProfile } from '../../services/kiraApiService';

// state 추가
const [companyProfile, setCompanyProfile] = useState<CompanyProfile | null>(null);

useEffect(() => {
  getCompanyProfile().then(p => setCompanyProfile(p)).catch(() => {});
}, []);
```

검색바 아래, 칩 위에 맞춤 추천 섹션 추가:

```tsx
{companyProfile?.companyName && companyProfile.regions.length > 0 && (
  <div className="rounded-xl border border-kira-200 bg-kira-50/50 p-4 mb-4">
    <h3 className="text-sm font-semibold text-slate-900 mb-2">
      🏢 {companyProfile.companyName} 맞춤 추천
    </h3>
    <p className="text-xs text-slate-500 mb-3">
      회사 업종({companyProfile.businessType})과 지역({companyProfile.regions.join(', ')}) 기반 추천 기관
    </p>
    <div className="flex flex-wrap gap-2">
      {/* 백엔드에서 추천 기관 목록을 가져오는 API 호출 or 정적 매핑 */}
    </div>
  </div>
)}
```

**Step 2: 발주계획 적합도 뱃지**

OrderPlansSection에서 각 발주계획의 적합도를 계산:

```typescript
function getRelevanceBadge(plan: OrderPlan, profile: CompanyProfile | null): { text: string; cls: string } | null {
  if (!profile) return null;
  let score = 0;
  // 지역 매칭
  if (profile.regions.some(r => plan.cnstwkRgnNm?.includes(r) || plan.jrsdctnDivNm?.includes(r))) score++;
  // 업종 매칭
  if (profile.specializations.some(s => plan.bizNm?.includes(s) || plan.category?.includes(s))) score++;
  // 경험 매칭
  if (profile.keyExperience.some(k => plan.bizNm?.includes(k) || plan.usgCntnts?.includes(k))) score++;

  if (score >= 2) return { text: '높음', cls: 'bg-emerald-100 text-emerald-700' };
  if (score >= 1) return { text: '보통', cls: 'bg-amber-100 text-amber-700' };
  return null;
}
```

테이블 각 행에 뱃지 렌더링.

**Step 3: 백엔드 — 맞춤 기관 추천 API (선택)**

`services/web_app/main.py`에 추가:

```python
@app.post("/api/forecast/recommend")
async def recommend_agencies(request: Request) -> dict[str, Any]:
    """회사 프로필 기반 관련 기관 추천."""
    username = _require_username(request)
    profile = _load_company_profile(username)
    if not profile:
        return {"agencies": []}

    # 회사 업종/지역 기반 추천 로직
    keywords = profile.get("specializations", []) + profile.get("keyExperience", [])
    regions = profile.get("regions", [])

    # 간단한 추천: 키워드로 나라장터 검색하여 빈도 높은 기관 추출
    from services.web_app.nara_api import search_bids
    org_counter: dict[str, int] = {}
    for kw in keywords[:3]:
        try:
            results = await search_bids(keywords=[kw], page_size=20)
            for bid in results.get("items", []):
                org = bid.get("issuingOrg") or bid.get("demandOrg", "")
                if org:
                    org_counter[org] = org_counter.get(org, 0) + 1
        except Exception:
            pass

    sorted_orgs = sorted(org_counter.items(), key=lambda x: -x[1])
    return {"agencies": [org for org, _ in sorted_orgs[:8]]}
```

**Step 4: 빌드 + 커밋**

```bash
cd frontend/kirabot && npm run build
git add frontend/kirabot/components/forecast/ForecastPage.tsx services/web_app/main.py
git commit -m "feat: add company-based forecast recommendations + relevance badges"
```

---

## Task 10: 최종 통합 테스트 + 정리

**Step 1: 전체 빌드 확인**

```bash
cd frontend/kirabot && npm run build
```

**Step 2: 서버 재시작**

```bash
kill $(lsof -ti:8000) && sleep 2 && python services/web_app/main.py &
```

**Step 3: E2E 검증 체크리스트**

- [ ] 사이드바: 3개 내비 (채팅, 알림설정, 발주예측)
- [ ] 사이드바 프로필 클릭 → 팝오버 메뉴 (설정, 홈, 로그아웃)
- [ ] 팝오버 > 설정 → /settings/general 이동
- [ ] /settings 사이드바 숨김 + 좌측탭 레이아웃
- [ ] /settings/general: 프로필 + 테마
- [ ] /settings/company: 폼 + 문서 업로드 + AI 추출
- [ ] /settings/usage: 기존 대시보드 내용
- [ ] /settings/account: 로그아웃 + 계정삭제
- [ ] /dashboard → /settings/usage 리다이렉트
- [ ] /settings/alerts: 기존 알림 설정 (사이드바에서 접근)
- [ ] 채팅: 회사 프로필 있으면 자동 연동 뱃지
- [ ] 발주예측: 맞춤 추천 + 적합도 뱃지

**Step 4: 최종 커밋**

```bash
git add -A
git commit -m "feat: complete settings page redesign + company info management system"
```
