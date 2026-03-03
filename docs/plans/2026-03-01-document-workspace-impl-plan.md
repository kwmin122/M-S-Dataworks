# Document Workspace Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 사용자가 profile.md, RFP 분석결과, 생성 문서를 웹에서 편집하고, 수정본 업로드로 학습시키는 통합 문서 워크스페이스.

**Architecture:** `/settings/documents` 라우트에 탭 기반 워크스페이스. 백엔드 API(rag_engine) + 프록시(web_app) + React 프론트엔드. 모든 편집 → diff_tracker → auto_learner 학습 연동.

**Tech Stack:** React 19 + TypeScript + Tailwind + Lucide, FastAPI + Pydantic, 기존 company_profile_updater/diff_tracker/auto_learner 재활용.

---

## Phase 1: profile.md 편집 API + UI

### Task 1: profile.md REST API (rag_engine)

**Files:**
- Modify: `rag_engine/main.py`
- Test: `rag_engine/tests/test_profile_md_api.py`

**Step 1: Write failing tests**

```python
# rag_engine/tests/test_profile_md_api.py
"""Tests for profile.md CRUD API endpoints."""
import os, json, pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("main._get_company_skills_dir", lambda cid="default": str(tmp_path / cid))
    from main import app
    return TestClient(app)

@pytest.fixture
def seeded_profile(tmp_path):
    """Create a profile.md with standard sections."""
    d = tmp_path / "demo"
    d.mkdir()
    (d / "profile.md").write_text(
        "# Demo 회사 프로필\n\n## 문서 스타일\n구조 패턴: A→B\n\n## 문체\n경어체\n\n"
        "## 강점 표현 패턴\nCCTV, 보안\n\n## 평가항목별 전략\n| 항목 | 비중 |\n\n"
        "## HWPX 생성 규칙\n본문: 맑은 고딕\n\n## 학습 이력\n- 초기 생성\n",
        encoding="utf-8",
    )
    return "demo"

class TestGetProfileMd:
    def test_returns_sections(self, client, seeded_profile):
        resp = client.get(f"/api/company-profile/md?company_id={seeded_profile}")
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data
        assert len(data["sections"]) >= 6
        assert data["sections"][0]["name"] == "문서 스타일"

    def test_missing_profile_returns_empty(self, client):
        resp = client.get("/api/company-profile/md?company_id=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["sections"] == []

class TestUpdateProfileSection:
    def test_update_section(self, client, seeded_profile):
        resp = client.put("/api/company-profile/md/section", json={
            "company_id": seeded_profile,
            "section_name": "문체",
            "content": "- 문체 유형: 격식체\n- 평균 문장 길이: 42자",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["version"] >= 1

    def test_update_nonexistent_section(self, client, seeded_profile):
        resp = client.put("/api/company-profile/md/section", json={
            "company_id": seeded_profile,
            "section_name": "없는섹션",
            "content": "test",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is False

class TestProfileHistory:
    def test_get_history(self, client, seeded_profile):
        # First create a version by updating
        client.put("/api/company-profile/md/section", json={
            "company_id": seeded_profile, "section_name": "문체", "content": "변경",
        })
        resp = client.get(f"/api/company-profile/md/history?company_id={seeded_profile}")
        assert resp.status_code == 200
        assert len(resp.json()["versions"]) >= 1

    def test_rollback(self, client, seeded_profile):
        # Update twice to create versions
        client.put("/api/company-profile/md/section", json={
            "company_id": seeded_profile, "section_name": "문체", "content": "v2",
        })
        client.put("/api/company-profile/md/section", json={
            "company_id": seeded_profile, "section_name": "문체", "content": "v3",
        })
        resp = client.post("/api/company-profile/md/rollback", json={
            "company_id": seeded_profile, "target_version": 1,
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
```

**Step 2: Run tests to verify they fail**

```bash
cd rag_engine && pytest tests/test_profile_md_api.py -v
```
Expected: FAIL (endpoints don't exist yet)

**Step 3: Implement 4 endpoints in main.py**

Add to `rag_engine/main.py`:

```python
# --- Profile.md CRUD ---

class UpdateProfileSectionRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=256)
    section_name: str = Field(min_length=1, max_length=256)
    content: str = Field(max_length=50_000)

class RollbackProfileRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=256)
    target_version: int = Field(ge=1)

def _get_company_skills_dir(company_id: str = "default") -> str:
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "company_skills")
    return os.path.join(base, company_id)

def _parse_profile_sections(content: str) -> list[dict]:
    """Parse profile.md into sections [{name, content, editable}]."""
    sections = []
    current_name = ""
    current_lines: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_name:
                sections.append({
                    "name": current_name,
                    "content": "\n".join(current_lines).strip(),
                    "editable": current_name != "학습 이력",
                })
            current_name = line[3:].strip()
            current_lines = []
        elif current_name:
            current_lines.append(line)

    if current_name:
        sections.append({
            "name": current_name,
            "content": "\n".join(current_lines).strip(),
            "editable": current_name != "학습 이력",
        })
    return sections

@app.get("/api/company-profile/md")
async def get_profile_md(company_id: str = "default") -> dict:
    skills_dir = _get_company_skills_dir(company_id)
    profile_path = os.path.join(skills_dir, "profile.md")
    if not os.path.isfile(profile_path):
        return {"sections": [], "metadata": {"version": 0, "company_id": company_id}}
    with open(profile_path, encoding="utf-8") as f:
        content = f.read()
    sections = _parse_profile_sections(content)
    from company_profile_updater import load_changelog
    changelog = load_changelog(skills_dir)
    version = len(changelog.get("versions", []))
    return {"sections": sections, "metadata": {"version": version, "company_id": company_id}}

@app.put("/api/company-profile/md/section")
async def update_profile_section_api(req: UpdateProfileSectionRequest) -> dict:
    from company_profile_updater import update_profile_section, load_changelog
    skills_dir = _get_company_skills_dir(req.company_id)
    success = update_profile_section(skills_dir, req.section_name, req.content)
    changelog = load_changelog(skills_dir)
    version = len(changelog.get("versions", []))
    return {"success": success, "version": version}

@app.get("/api/company-profile/md/history")
async def get_profile_history(company_id: str = "default") -> dict:
    from company_profile_updater import load_changelog
    skills_dir = _get_company_skills_dir(company_id)
    changelog = load_changelog(skills_dir)
    return {"versions": changelog.get("versions", []), "current_version": len(changelog.get("versions", []))}

@app.post("/api/company-profile/md/rollback")
async def rollback_profile(req: RollbackProfileRequest) -> dict:
    import glob as _glob
    skills_dir = _get_company_skills_dir(req.company_id)
    history_dir = os.path.join(skills_dir, "profile_history")
    target_file = os.path.join(history_dir, f"profile_v{req.target_version:03d}.md")
    if not os.path.isfile(target_file):
        return {"success": False, "error": f"Version {req.target_version} not found"}
    with open(target_file, encoding="utf-8") as f:
        content = f.read()
    # Backup current before rollback
    from company_profile_updater import backup_profile_version
    backup_profile_version(skills_dir, reason=f"rollback to v{req.target_version}")
    profile_path = os.path.join(skills_dir, "profile.md")
    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"success": True, "restored_version": req.target_version}
```

**Step 4: Run tests**

```bash
cd rag_engine && pytest tests/test_profile_md_api.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add rag_engine/main.py rag_engine/tests/test_profile_md_api.py
git commit -m "feat: add profile.md CRUD API endpoints (GET/PUT/history/rollback)"
```

---

### Task 2: web_app 프록시 엔드포인트

**Files:**
- Modify: `services/web_app/main.py`

**Step 1: Add proxy endpoints**

web_app에서 rag_engine의 profile.md API를 프록시하는 4개 엔드포인트 추가. 기존 `_proxy_to_rag` 패턴이 없으면 httpx 직접 호출 패턴 사용.

```python
# GET /api/profile-md?company_id=xxx → rag_engine GET /api/company-profile/md
# PUT /api/profile-md/section → rag_engine PUT /api/company-profile/md/section
# GET /api/profile-md/history?company_id=xxx → rag_engine GET /api/company-profile/md/history
# POST /api/profile-md/rollback → rag_engine POST /api/company-profile/md/rollback
```

기존 web_app의 프록시 패턴(httpx.AsyncClient, timeout=30, status check) 참고하여 구현.

**Step 2: Run existing tests to ensure no regression**

```bash
cd rag_engine && pytest -q
```
Expected: 227+ passed

**Step 3: Commit**

```bash
git add services/web_app/main.py
git commit -m "feat: add profile-md proxy endpoints in web_app"
```

---

### Task 3: TypeScript 타입 + API 서비스

**Files:**
- Modify: `frontend/kirabot/src/types/global.d.ts`
- Modify: `frontend/kirabot/src/services/kiraApiService.ts`

**Step 1: Add TypeScript types**

```typescript
// types/global.d.ts — 추가
export interface ProfileSection {
  name: string;
  content: string;
  editable: boolean;
}

export interface ProfileMdResponse {
  sections: ProfileSection[];
  metadata: { version: number; company_id: string };
}

export interface ProfileVersion {
  version: number;
  date: string;
  reason: string;
}

export interface ProfileHistoryResponse {
  versions: ProfileVersion[];
  current_version: number;
}

export interface DocumentInfo {
  id: string;
  type: 'proposal' | 'wbs' | 'ppt' | 'track_record';
  title: string;
  created_at: string;
  filename: string;
}

export interface DocumentSections {
  sections: Array<{ name: string; content: string }>;
  metadata: { doc_id: string; type: string };
}

export interface DiffResult {
  success: boolean;
  diff_count: number;
  learned_patterns: string[];
}

export interface RevisionResult {
  success: boolean;
  diffs: Array<{ section: string; diff_type: string }>;
  learned_patterns: string[];
}
```

**Step 2: Add API functions**

```typescript
// kiraApiService.ts — 추가

// Profile.md
export async function getProfileMd(companyId = 'default'): Promise<ProfileMdResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/profile-md?company_id=${encodeURIComponent(companyId)}`);
  return parseJson<ProfileMdResponse>(res);
}

export async function updateProfileSection(
  companyId: string, sectionName: string, content: string,
): Promise<{ success: boolean; version: number }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/profile-md/section`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_id: companyId, section_name: sectionName, content }),
  });
  return parseJson(res);
}

export async function getProfileHistory(companyId = 'default'): Promise<ProfileHistoryResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/profile-md/history?company_id=${encodeURIComponent(companyId)}`);
  return parseJson<ProfileHistoryResponse>(res);
}

export async function rollbackProfile(
  companyId: string, targetVersion: number,
): Promise<{ success: boolean; restored_version?: number; error?: string }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/profile-md/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_id: companyId, target_version: targetVersion }),
  });
  return parseJson(res);
}
```

**Step 3: Commit**

```bash
git add frontend/kirabot/src/types/global.d.ts frontend/kirabot/src/services/kiraApiService.ts
git commit -m "feat: add profile-md TypeScript types and API service functions"
```

---

### Task 4: DocumentWorkspace 레이아웃 + 라우팅

**Files:**
- Create: `frontend/kirabot/src/pages/SettingsDocuments.tsx`
- Create: `frontend/kirabot/src/components/settings/documents/DocumentWorkspace.tsx`
- Create: `frontend/kirabot/src/components/settings/documents/DocumentTabNav.tsx`
- Modify: `frontend/kirabot/src/App.tsx` (add route)
- Modify: `frontend/kirabot/src/pages/SettingsPage.tsx` (add tab)

**Step 1: Create DocumentTabNav**

```tsx
// components/settings/documents/DocumentTabNav.tsx
import React from 'react';
import { Settings, FileText, ClipboardList, CalendarDays, Presentation } from 'lucide-react';

export type DocumentTab = 'profile' | 'rfp' | 'proposal' | 'wbs' | 'ppt';

interface Props {
  activeTab: DocumentTab;
  onTabChange: (tab: DocumentTab) => void;
  documentCounts?: Partial<Record<DocumentTab, number>>;
}

const TABS: Array<{ id: DocumentTab; label: string; icon: React.ElementType }> = [
  { id: 'profile', label: '회사 프로필', icon: Settings },
  { id: 'rfp', label: 'RFP 분석', icon: ClipboardList },
  { id: 'proposal', label: '제안서', icon: FileText },
  { id: 'wbs', label: 'WBS', icon: CalendarDays },
  { id: 'ppt', label: 'PPT', icon: Presentation },
];

export default function DocumentTabNav({ activeTab, onTabChange, documentCounts }: Props) {
  return (
    <nav className="w-40 shrink-0 border-r border-slate-200 py-4 px-2 space-y-0.5">
      <h3 className="px-3 pb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">문서</h3>
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        const count = documentCounts?.[tab.id];
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
              isActive
                ? 'bg-kira-50 text-kira-700 font-semibold border-l-2 border-kira-500 -ml-px'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <Icon size={16} className="shrink-0" />
            <span className="flex-1 text-left">{tab.label}</span>
            {count != null && count > 0 && (
              <span className="text-xs text-slate-400">{count}</span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
```

**Step 2: Create DocumentWorkspace**

```tsx
// components/settings/documents/DocumentWorkspace.tsx
import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import DocumentTabNav, { type DocumentTab } from './DocumentTabNav';
import ProfileEditor from './ProfileEditor';

export default function DocumentWorkspace() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get('tab') as DocumentTab) || 'profile';

  const handleTabChange = (tab: DocumentTab) => {
    setSearchParams({ tab });
  };

  return (
    <div className="flex flex-1 min-h-0">
      <DocumentTabNav activeTab={activeTab} onTabChange={handleTabChange} />
      <div className="flex-1 overflow-y-auto p-6 lg:p-8">
        <div className="max-w-4xl mx-auto">
          {activeTab === 'profile' && <ProfileEditor />}
          {activeTab === 'rfp' && <PlaceholderTab name="RFP 분석결과" />}
          {activeTab === 'proposal' && <PlaceholderTab name="제안서" />}
          {activeTab === 'wbs' && <PlaceholderTab name="WBS" />}
          {activeTab === 'ppt' && <PlaceholderTab name="PPT" />}
        </div>
      </div>
    </div>
  );
}

function PlaceholderTab({ name }: { name: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-400">
      {name} 편집 (준비 중)
    </div>
  );
}
```

**Step 3: Create SettingsDocuments page**

```tsx
// pages/SettingsDocuments.tsx
import React from 'react';
import DocumentWorkspace from '../components/settings/documents/DocumentWorkspace';

export default function SettingsDocuments() {
  return <DocumentWorkspace />;
}
```

**Step 4: Add route in App.tsx and tab in SettingsPage.tsx**

App.tsx — 기존 Settings Route 안에:
```tsx
<Route path="documents" element={<SettingsDocuments />} />
```

SettingsPage.tsx — tabs 배열에:
```typescript
{ path: 'documents', label: '문서 관리', icon: FileText },
```

**Step 5: Commit**

```bash
git add frontend/kirabot/src/
git commit -m "feat: add DocumentWorkspace layout with tab navigation and routing"
```

---

### Task 5: ProfileEditor + ProfileSection 컴포넌트

**Files:**
- Create: `frontend/kirabot/src/components/settings/documents/ProfileEditor.tsx`
- Create: `frontend/kirabot/src/components/settings/documents/ProfileSection.tsx`

**Step 1: ProfileSection — 개별 섹션 카드 (읽기/편집 토글)**

```tsx
// components/settings/documents/ProfileSection.tsx
import React, { useState } from 'react';
import { Pencil, Save, X, History } from 'lucide-react';

interface Props {
  name: string;
  content: string;
  editable: boolean;
  onSave: (name: string, content: string) => Promise<void>;
  onShowHistory?: () => void;
}

export default function ProfileSection({ name, content, editable, onSave, onShowHistory }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(name, draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setDraft(content);
    setEditing(false);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold text-slate-800">## {name}</h3>
        <div className="flex items-center gap-1.5">
          {onShowHistory && (
            <button onClick={onShowHistory} className="text-slate-400 hover:text-slate-600 p-1" title="버전 이력">
              <History size={16} />
            </button>
          )}
          {editable && !editing && (
            <button onClick={() => setEditing(true)} className="text-slate-400 hover:text-kira-600 p-1" title="편집">
              <Pencil size={16} />
            </button>
          )}
        </div>
      </div>

      {editing ? (
        <div className="space-y-3">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.max(4, draft.split('\n').length + 1)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none resize-y"
          />
          <div className="flex gap-2 justify-end">
            <button onClick={handleCancel} className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
              <X size={14} /> 취소
            </button>
            <button onClick={handleSave} disabled={saving} className="flex items-center gap-1 rounded-lg bg-kira-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-kira-700 disabled:opacity-50">
              <Save size={14} /> {saving ? '저장 중...' : '저장'}
            </button>
          </div>
        </div>
      ) : (
        <pre className="text-sm text-slate-600 whitespace-pre-wrap font-sans leading-relaxed">{content || '(비어있음)'}</pre>
      )}
    </div>
  );
}
```

**Step 2: ProfileEditor — 전체 프로필 편집 페이지**

```tsx
// components/settings/documents/ProfileEditor.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { Settings, RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';
import ProfileSection from './ProfileSection';
import VersionHistory from './VersionHistory';
import { getProfileMd, updateProfileSection, getProfileHistory, rollbackProfile } from '../../../services/kiraApiService';
import type { ProfileSection as ProfileSectionType, ProfileVersion } from '../../../types';

export default function ProfileEditor() {
  const [sections, setSections] = useState<ProfileSectionType[]>([]);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<ProfileVersion[]>([]);
  const [saveMsg, setSaveMsg] = useState('');
  const companyId = 'default'; // TODO: from context/session

  const loadProfile = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getProfileMd(companyId);
      setSections(data.sections);
      setVersion(data.metadata.version);
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : '프로필 로드 실패');
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  const handleSave = async (sectionName: string, content: string) => {
    const result = await updateProfileSection(companyId, sectionName, content);
    if (result.success) {
      setVersion(result.version);
      setSaveMsg('저장되었습니다.');
      setTimeout(() => setSaveMsg(''), 3000);
      await loadProfile(); // Refresh sections
    } else {
      throw new Error('섹션을 찾을 수 없습니다.');
    }
  };

  const handleShowHistory = async () => {
    const data = await getProfileHistory(companyId);
    setHistory(data.versions);
    setShowHistory(true);
  };

  const handleRollback = async (targetVersion: number) => {
    const result = await rollbackProfile(companyId, targetVersion);
    if (result.success) {
      setShowHistory(false);
      setSaveMsg(`v${targetVersion}으로 되돌렸습니다.`);
      setTimeout(() => setSaveMsg(''), 3000);
      await loadProfile();
    }
  };

  if (loading) {
    return <div className="text-center text-slate-400 py-12">프로필 로드 중...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings size={20} className="text-kira-600" />
          <h2 className="text-lg font-semibold text-slate-900">회사 프로필</h2>
          {version > 0 && <span className="text-xs text-slate-400">v{version}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleShowHistory} className="flex items-center gap-1 text-xs text-slate-500 hover:text-kira-600">
            <RefreshCw size={14} /> 버전 이력
          </button>
        </div>
      </div>

      {sections.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
          <p className="text-sm text-slate-500">프로필이 아직 생성되지 않았습니다.</p>
          <p className="text-xs text-slate-400 mt-1">회사 문서를 업로드하면 자동으로 생성됩니다.</p>
        </div>
      ) : (
        sections.map((s) => (
          <ProfileSection
            key={s.name}
            name={s.name}
            content={s.content}
            editable={s.editable}
            onSave={handleSave}
            onShowHistory={s.editable ? handleShowHistory : undefined}
          />
        ))
      )}

      {showHistory && (
        <VersionHistory
          versions={history}
          onRollback={handleRollback}
          onClose={() => setShowHistory(false)}
        />
      )}

      {saveMsg && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl border border-emerald-200 bg-emerald-50 shadow-lg px-5 py-3 text-sm text-emerald-700"
        >
          {saveMsg}
        </motion.div>
      )}
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/kirabot/src/components/settings/documents/
git commit -m "feat: add ProfileEditor and ProfileSection components"
```

---

### Task 6: VersionHistory 컴포넌트

**Files:**
- Create: `frontend/kirabot/src/components/settings/documents/VersionHistory.tsx`

```tsx
// components/settings/documents/VersionHistory.tsx
import React from 'react';
import { X, RotateCcw, Clock } from 'lucide-react';
import type { ProfileVersion } from '../../../types';

interface Props {
  versions: ProfileVersion[];
  onRollback: (version: number) => void;
  onClose: () => void;
}

export default function VersionHistory({ versions, onRollback, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h3 className="text-base font-semibold text-slate-800">버전 이력</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto p-4 space-y-2">
          {versions.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">버전 이력이 없습니다.</p>
          ) : (
            versions.slice().reverse().map((v) => (
              <div key={v.version} className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3 hover:bg-slate-50">
                <div className="flex items-center gap-3">
                  <Clock size={14} className="text-slate-400" />
                  <div>
                    <span className="text-sm font-medium text-slate-700">v{v.version}</span>
                    <span className="ml-2 text-xs text-slate-400">{v.date}</span>
                    {v.reason && <p className="text-xs text-slate-500 mt-0.5">{v.reason}</p>}
                  </div>
                </div>
                <button
                  onClick={() => onRollback(v.version)}
                  className="flex items-center gap-1 text-xs text-kira-600 hover:text-kira-700"
                >
                  <RotateCcw size={12} /> 되돌리기
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
```

**Commit:**
```bash
git add frontend/kirabot/src/components/settings/documents/VersionHistory.tsx
git commit -m "feat: add VersionHistory modal component"
```

---

## Phase 2: RFP 분석결과 편집

### Task 7: RFP 분석결과 API

**Files:**
- Modify: `services/web_app/main.py`

RFP 분석결과는 web_app의 세션(메모리)에 저장되어 있음. `session.latest_rfx_analysis`를 읽고/수정하는 2개 엔드포인트 추가:

```python
# GET /api/rfp-analysis/latest?session_id=xxx
#   → session.latest_rfx_analysis를 JSON으로 반환
# PUT /api/rfp-analysis/update
#   body: {session_id, requirements?, evaluation_criteria?, rfp_text_summary?}
#   → session.latest_rfx_analysis 필드 업데이트
```

세션의 `latest_rfx_analysis` 객체 필드를 부분 업데이트하는 패턴. requirements와 evaluation_criteria는 리스트로 전체 교체.

**Commit:**
```bash
git add services/web_app/main.py
git commit -m "feat: add RFP analysis read/update API endpoints"
```

---

### Task 8: RfpEditor + RequirementEditor 컴포넌트

**Files:**
- Create: `frontend/kirabot/src/components/settings/documents/RfpEditor.tsx`
- Create: `frontend/kirabot/src/components/settings/documents/RequirementEditor.tsx`

RfpEditor: 자격요건 리스트(RequirementEditor) + 평가기준 테이블 + RFP 요약 마크다운 편집. 각 섹션은 ProfileSection과 유사한 카드+편집 패턴.

RequirementEditor: 자격요건 항목별 추가/삭제/수정. ChipInput 패턴 참고.

DocumentWorkspace.tsx에서 `activeTab === 'rfp'` 조건에 RfpEditor 렌더링.

**Commit:**
```bash
git add frontend/kirabot/src/components/settings/documents/
git commit -m "feat: add RfpEditor and RequirementEditor components"
```

---

## Phase 3: 제안서 웹 편집

### Task 9: 생성 문서 관리 API (rag_engine)

**Files:**
- Modify: `rag_engine/main.py`
- Test: `rag_engine/tests/test_document_editor_api.py`

3개 엔드포인트:

```python
# GET /api/documents/list?session_id=xxx
#   → data/proposals/ 디렉토리에서 해당 세션 파일 목록 반환
# GET /api/documents/{filename}/sections
#   → DOCX 파일의 섹션별 텍스트 추출 (document_assembler 역변환 또는 저장된 sections 활용)
# PUT /api/documents/{filename}/section
#   body: {section_name, new_content, company_id?}
#   → diff_tracker + auto_learner 호출 + sections 업데이트
```

핵심: 제안서 생성 시 sections를 JSON으로도 저장 (`{filename}.sections.json`). 편집 시 이 JSON을 수정하고 DOCX를 재조립.

**Commit:**
```bash
git add rag_engine/main.py rag_engine/tests/test_document_editor_api.py
git commit -m "feat: add document sections CRUD API with diff learning"
```

---

### Task 10: ProposalEditor + DocumentSection 컴포넌트

**Files:**
- Create: `frontend/kirabot/src/components/settings/documents/ProposalEditor.tsx`
- Create: `frontend/kirabot/src/components/settings/documents/DocumentSection.tsx`

DocumentSection: 공통 마크다운 섹션 편집 카드 (ProfileSection과 유사하나 diff 학습 연동).

ProposalEditor: 상단에 문서 정보 + 섹션 리스트 + 하단에 [재다운로드] [재생성] 버튼.

DocumentWorkspace.tsx에서 `activeTab === 'proposal'` + `searchParams.get('id')` 로 특정 제안서 편집.

**Commit:**
```bash
git add frontend/kirabot/src/components/settings/documents/
git commit -m "feat: add ProposalEditor and DocumentSection components"
```

---

## Phase 4: 파일 업로드 학습

### Task 11: 수정본 업로드 API

**Files:**
- Modify: `rag_engine/main.py`

```python
# POST /api/documents/{filename}/upload-revision
#   body: FormData(file=수정본_DOCX)
#   → 원본 sections.json 로드
#   → 수정본 DOCX에서 텍스트 추출 (document_parser)
#   → 섹션별 diff 비교
#   → auto_learner.process_edit_feedback() 호출
#   → {success, diffs: [...], learned_patterns: [...]} 반환
```

**Commit:**
```bash
git add rag_engine/main.py
git commit -m "feat: add document revision upload endpoint with diff learning"
```

---

### Task 12: FileUploadZone + DiffPreview 컴포넌트

**Files:**
- Create: `frontend/kirabot/src/components/settings/documents/FileUploadZone.tsx`
- Create: `frontend/kirabot/src/components/settings/documents/DiffPreview.tsx`

FileUploadZone: 드래그&드롭 영역 + [원본 다운로드] 버튼. 업로드 후 DiffPreview 표시.

DiffPreview: diff 결과를 섹션별로 표시 (추가/삭제/변경 색상 구분). learned_patterns 알림.

ProposalEditor 하단에 FileUploadZone 통합 (웹편집/파일업로드 탭 전환).

**Commit:**
```bash
git add frontend/kirabot/src/components/settings/documents/
git commit -m "feat: add FileUploadZone and DiffPreview components"
```

---

## Phase 5: WBS/PPT 편집

### Task 13: WbsEditor + PptEditor 컴포넌트

**Files:**
- Create: `frontend/kirabot/src/components/settings/documents/WbsEditor.tsx`
- Create: `frontend/kirabot/src/components/settings/documents/PptEditor.tsx`

ProposalEditor 패턴 재사용. 차이점:
- WbsEditor: XLSX + 간트차트(PNG) + DOCX 3개 파일. 태스크 리스트 테이블 편집.
- PptEditor: PPTX + QnA 리스트. 슬라이드별 콘텐츠 편집.

둘 다 FileUploadZone 하단에 포함.

DocumentWorkspace.tsx의 `activeTab === 'wbs' | 'ppt'` 조건에 연결.

**Commit:**
```bash
git add frontend/kirabot/src/components/settings/documents/
git commit -m "feat: add WbsEditor and PptEditor components"
```

---

## Phase 6: 채팅 연동

### Task 14: 채팅 메시지에 [편집] 버튼 추가

**Files:**
- Modify: `frontend/kirabot/src/types/global.d.ts` (MessageAction 추가)
- Modify: `frontend/kirabot/src/components/chat/messages/AnalysisResultView.tsx`
- Modify: `frontend/kirabot/src/hooks/useConversationFlow.ts`

**Step 1: MessageAction 타입 추가**

```typescript
// types/global.d.ts — MessageAction union에 추가
| { type: 'edit_document'; docType: 'proposal' | 'wbs' | 'ppt' | 'track_record'; docId: string }
```

**Step 2: AnalysisResultView에 [편집] 버튼 추가**

생성 완료 메시지(다운로드 링크 옆)에 [편집] 버튼 추가. 클릭 시 `onAction({ type: 'edit_document', docType, docId })`.

**Step 3: useConversationFlow에서 라우팅 처리**

`edit_document` 액션 → `navigate('/settings/documents?tab={docType}&id={docId}')`.

**Commit:**
```bash
git add frontend/kirabot/src/
git commit -m "feat: add [편집] button in chat messages linking to document workspace"
```

---

## 전체 검증

```bash
# 1. Python 테스트
cd rag_engine && pytest -q
# 기대: 230+ passed (기존 227 + 신규 ~6)

# 2. TypeScript 타입 체크
cd frontend/kirabot && npx tsc --noEmit

# 3. 프론트엔드 빌드
cd frontend/kirabot && npm run build

# 4. 수동 테스트 시나리오
# a) /settings/documents → 프로필 탭 → 섹션 편집 → 저장 → 버전 확인
# b) RFP 탭 → 자격요건 편집 → 저장
# c) 제안서 탭 → 섹션 편집 → diff 학습 확인
# d) 제안서 탭 → 파일 업로드 → diff 결과 확인
# e) 채팅 → [편집] 클릭 → 문서 워크스페이스로 이동
```

## 수정 파일 요약

| Phase | 파일 | 변경 |
|-------|------|------|
| P1 | `rag_engine/main.py` | profile.md CRUD 4개 엔드포인트 |
| P1 | `rag_engine/tests/test_profile_md_api.py` | 테스트 ~8개 |
| P1 | `services/web_app/main.py` | 프록시 4개 |
| P1 | `frontend/.../types/global.d.ts` | ProfileSection, ProfileVersion 등 타입 |
| P1 | `frontend/.../kiraApiService.ts` | API 함수 4개 |
| P1 | `frontend/.../SettingsDocuments.tsx` | 라우트 페이지 |
| P1 | `frontend/.../DocumentWorkspace.tsx` | 메인 레이아웃 |
| P1 | `frontend/.../DocumentTabNav.tsx` | 탭 네비게이션 |
| P1 | `frontend/.../ProfileEditor.tsx` | 프로필 편집 |
| P1 | `frontend/.../ProfileSection.tsx` | 섹션 카드 |
| P1 | `frontend/.../VersionHistory.tsx` | 버전 모달 |
| P1 | `frontend/.../App.tsx` | 라우트 추가 |
| P1 | `frontend/.../SettingsPage.tsx` | 탭 추가 |
| P2 | `services/web_app/main.py` | RFP 읽기/수정 API |
| P2 | `frontend/.../RfpEditor.tsx` | RFP 편집 |
| P2 | `frontend/.../RequirementEditor.tsx` | 요건 리스트 |
| P3 | `rag_engine/main.py` | 문서 섹션 CRUD 3개 |
| P3 | `frontend/.../ProposalEditor.tsx` | 제안서 편집 |
| P3 | `frontend/.../DocumentSection.tsx` | 공통 섹션 편집 |
| P4 | `rag_engine/main.py` | 수정본 업로드 1개 |
| P4 | `frontend/.../FileUploadZone.tsx` | 업로드 영역 |
| P4 | `frontend/.../DiffPreview.tsx` | diff 미리보기 |
| P5 | `frontend/.../WbsEditor.tsx` | WBS 편집 |
| P5 | `frontend/.../PptEditor.tsx` | PPT 편집 |
| P6 | `frontend/.../AnalysisResultView.tsx` | [편집] 버튼 |
| P6 | `frontend/.../useConversationFlow.ts` | 라우팅 |
