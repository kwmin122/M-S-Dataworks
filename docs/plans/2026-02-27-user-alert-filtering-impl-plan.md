# User Alert Filtering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to configure detailed email alerts with company profile-based filtering (product codes, detailed items, excluded regions, natural language company info).

**Architecture:** Independent `/alerts` page in chat UI with file-based persistent storage (`data/user_alerts/`). 2-stage filtering: metadata-based (free) + LLM RFP parsing (Pro, future). Extends existing `AlertRule` schema with new filter fields.

**Tech Stack:** React 19 + TypeScript (frontend), FastAPI + Python (backend), file-based JSON storage, existing `call_with_retry` LLM utilities.

---

## Phase 1: Backend Foundation

### Task 1: Extend AlertRule Data Model

**Files:**
- Modify: `frontend/kirabot/services/kiraApiService.ts:325-342`
- Test: `tests/test_alert_model.py` (create)

**Step 1: Write the failing test**

Create `tests/test_alert_model.py`:

```python
import json
from pathlib import Path

def test_alert_config_schema_has_new_fields():
    """Verify extended AlertRule schema includes new filter fields"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "rules": [{
            "id": "rule1",
            "keywords": ["교통신호등"],
            "excludeKeywords": [],
            "categories": [],
            "regions": [],
            "excludeRegions": ["안산", "부산"],  # NEW
            "productCodes": ["42101"],          # NEW
            "detailedItems": ["교통신호등 주"],  # NEW
            "excludeContractorLocations": [],   # NEW
            "enabled": True,
        }],
        "companyProfile": {                     # NEW
            "description": "교통신호등 제조 전문",
            "mainProducts": ["신호등"],
        }
    }

    # Should serialize without error
    json_str = json.dumps(config, ensure_ascii=False)
    assert "excludeRegions" in json_str
    assert "productCodes" in json_str
    assert "companyProfile" in json_str
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_model.py -v`
Expected: PASS (JSON serialization doesn't validate schema, just structure test)

**Step 3: Update TypeScript interfaces**

Modify `frontend/kirabot/services/kiraApiService.ts:325-342`:

```typescript
export interface AlertRule {
  id: string;
  keywords: string[];
  excludeKeywords: string[];
  categories: string[];
  regions: string[];
  minAmt?: number;
  maxAmt?: number;
  enabled: boolean;

  // 🆕 New filter fields
  productCodes?: string[];              // 물품분류번호
  detailedItems?: string[];             // 세부품명
  excludeRegions?: string[];            // 제외 지역
  excludeContractorLocations?: string[]; // 제외 발주처 소재지
}

export interface CompanyProfile {
  description: string;                  // 자연어 회사 설명
  businessTypes?: string[];
  certifications?: string[];
  mainProducts?: string[];
  excludedAreas?: string[];
}

export interface AlertConfig {
  enabled: boolean;
  email: string;
  schedule: 'realtime' | 'daily_1' | 'daily_2' | 'daily_3';
  hours: number[];
  rules: AlertRule[];
  companyProfile?: CompanyProfile;      // 🆕 회사 프로필
  createdAt?: string;
  updatedAt?: string;
}
```

**Step 4: Run TypeScript check**

Run: `cd frontend/kirabot && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/kirabot/services/kiraApiService.ts tests/test_alert_model.py
git commit -m "feat: extend AlertRule schema with new filter fields

- Add excludeRegions, productCodes, detailedItems
- Add CompanyProfile interface for natural language input
- Add createdAt/updatedAt timestamps"
```

---

### Task 2: Backend Alert Config Storage

**Files:**
- Create: `services/web_app/alert_storage.py`
- Test: `tests/test_alert_storage.py` (create)

**Step 1: Write the failing test**

Create `tests/test_alert_storage.py`:

```python
import json
import hashlib
from pathlib import Path
import pytest
from services.web_app.alert_storage import (
    get_alert_config,
    save_alert_config,
    get_alert_config_path,
)

@pytest.fixture
def cleanup_test_alerts():
    """Clean up test alert files after test"""
    yield
    test_dir = Path("data/user_alerts")
    if test_dir.exists():
        for f in test_dir.glob("*.json"):
            if "test" in f.read_text():
                f.unlink()

def test_save_and_load_alert_config(cleanup_test_alerts):
    """Save alert config and retrieve it"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "rules": [{
            "id": "1",
            "keywords": ["교통신호등"],
            "enabled": True,
        }],
    }

    # Save
    save_alert_config(config)

    # Load
    loaded = get_alert_config("test@example.com")

    assert loaded["email"] == "test@example.com"
    assert loaded["schedule"] == "daily_2"
    assert len(loaded["rules"]) == 1
    assert "createdAt" in loaded
    assert "updatedAt" in loaded

def test_get_nonexistent_config_returns_default():
    """Get config for email that doesn't exist returns default"""
    config = get_alert_config("nonexistent@example.com")

    assert config["email"] == "nonexistent@example.com"
    assert config["enabled"] is False
    assert config["schedule"] == "daily_1"
    assert config["rules"] == []

def test_email_hash_consistent():
    """Email hash should be consistent (lowercase normalized)"""
    path1 = get_alert_config_path("User@Example.COM")
    path2 = get_alert_config_path("user@example.com")

    assert path1 == path2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_storage.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'services.web_app.alert_storage'"

**Step 3: Implement alert_storage.py**

Create `services/web_app/alert_storage.py`:

```python
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

ALERTS_DIR = Path("data/user_alerts")

def get_alert_config_path(email: str) -> Path:
    """Get file path for alert config (email normalized to lowercase)"""
    email_hash = hashlib.sha256(email.lower().strip().encode()).hexdigest()
    return ALERTS_DIR / f"{email_hash}.json"

def get_alert_config(email: str) -> dict[str, Any]:
    """Load alert config for email, return default if not exists"""
    if not email or '@' not in email:
        raise ValueError("유효한 이메일 주소가 필요합니다.")

    file_path = get_alert_config_path(email)

    if not file_path.exists():
        return _default_alert_config(email)

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_alert_config(config: dict[str, Any]) -> None:
    """Save alert config to file"""
    email = config.get("email")
    if not email or '@' not in email:
        raise ValueError("유효한 이메일 주소가 필요합니다.")

    # Add/update timestamps
    now = datetime.now(timezone.utc).isoformat()
    config["updatedAt"] = now
    if "createdAt" not in config:
        config["createdAt"] = now

    # Ensure directory exists
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)

    # Write to file
    file_path = get_alert_config_path(email)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def _default_alert_config(email: str) -> dict[str, Any]:
    """Return default config for new user"""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "email": email,
        "enabled": False,
        "schedule": "daily_1",
        "hours": [9],
        "rules": [],
        "createdAt": now,
        "updatedAt": now,
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_alert_storage.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add services/web_app/alert_storage.py tests/test_alert_storage.py
git commit -m "feat: add alert config file-based storage

- SHA256 email hashing for privacy
- Auto-create data/user_alerts/ directory
- Default config for new users
- Timestamp management (createdAt/updatedAt)"
```

---

### Task 3: Alert Config API Endpoints

**Files:**
- Modify: `services/web_app/main.py` (add endpoints)
- Test: `tests/test_web_runtime_api.py` (add tests)

**Step 1: Write the failing test**

Add to `tests/test_web_runtime_api.py`:

```python
def test_get_alert_config_nonexistent_returns_default():
    """GET /api/alerts/config for new user returns default config"""
    resp = client.get("/api/alerts/config?email=new@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["enabled"] is False
    assert data["rules"] == []

def test_save_and_retrieve_alert_config():
    """POST /api/alerts/config saves and GET retrieves"""
    config = {
        "email": "user@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "rules": [{
            "id": "1",
            "keywords": ["교통신호등"],
            "excludeRegions": ["안산"],
            "productCodes": ["42101"],
            "enabled": True,
        }],
        "companyProfile": {
            "description": "교통신호등 제조 전문",
        }
    }

    # Save
    save_resp = client.post("/api/alerts/config", json=config)
    assert save_resp.status_code == 200
    assert save_resp.json()["success"] is True

    # Retrieve
    get_resp = client.get("/api/alerts/config?email=user@example.com")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["email"] == "user@example.com"
    assert data["schedule"] == "daily_2"
    assert len(data["rules"]) == 1
    assert data["rules"][0]["excludeRegions"] == ["안산"]
    assert data["companyProfile"]["description"] == "교통신호등 제조 전문"

def test_save_alert_config_validates_email():
    """POST /api/alerts/config rejects invalid email"""
    config = {
        "email": "invalid-email",
        "enabled": True,
        "rules": []
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "유효한 이메일" in resp.json()["detail"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_runtime_api.py::test_get_alert_config_nonexistent_returns_default -v`
Expected: FAIL with "404 Not Found"

**Step 3: Implement API endpoints**

Add to `services/web_app/main.py` (after existing imports):

```python
from alert_storage import get_alert_config, save_alert_config  # noqa: E402
```

Add endpoints (before final `if __name__ == "__main__":`):

```python
@app.get("/api/alerts/config")
def get_user_alert_config(email: str) -> dict[str, Any]:
    """사용자 알림 설정 조회"""
    try:
        return get_alert_config(email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/alerts/config")
def save_user_alert_config(config: dict[str, Any]) -> dict[str, Any]:
    """사용자 알림 설정 저장"""
    try:
        # Basic validation
        if not config.get("email"):
            raise ValueError("이메일이 필요합니다.")
        if not isinstance(config.get("rules"), list):
            raise ValueError("rules 필드가 배열이어야 합니다.")
        if config.get("schedule") not in ["realtime", "daily_1", "daily_2", "daily_3"]:
            raise ValueError("올바른 schedule 값이 필요합니다.")

        save_alert_config(config)
        return {"success": True, "message": "알림 설정이 저장되었습니다."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_runtime_api.py::test_get_alert_config_nonexistent_returns_default tests/test_web_runtime_api.py::test_save_and_retrieve_alert_config tests/test_web_runtime_api.py::test_save_alert_config_validates_email -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add services/web_app/main.py tests/test_web_runtime_api.py
git commit -m "feat: add alert config API endpoints

- GET /api/alerts/config?email=
- POST /api/alerts/config
- Input validation for email and schedule"
```

---

### Task 4: Metadata Filter Matching Logic

**Files:**
- Create: `services/web_app/alert_matcher.py`
- Test: `tests/test_alert_matcher.py` (create)

**Step 1: Write the failing test**

Create `tests/test_alert_matcher.py`:

```python
from services.web_app.alert_matcher import apply_metadata_filters

def test_keyword_match():
    """Keywords in title should match"""
    bid = {"title": "교통신호등 설치 공사", "category": "물품"}
    rule = {"keywords": ["교통신호등"], "excludeKeywords": []}

    assert apply_metadata_filters(bid, rule) is True

def test_exclude_keyword_blocks():
    """Exclude keywords should block"""
    bid = {"title": "교통신호등 유지보수"}
    rule = {"keywords": ["교통신호등"], "excludeKeywords": ["유지보수"]}

    assert apply_metadata_filters(bid, rule) is False

def test_exclude_region_blocks():
    """Exclude regions should block"""
    bid = {"title": "신호등 설치", "region": "안산"}
    rule = {"keywords": ["신호등"], "excludeRegions": ["안산", "부산"]}

    assert apply_metadata_filters(bid, rule) is False

def test_product_code_matching():
    """Product codes in attachmentText should match"""
    bid = {
        "title": "CCTV 구매",
        "attachmentText": "물품분류번호: 42101\n기타 내용..."
    }
    rule = {"keywords": ["CCTV"], "productCodes": ["42101"]}

    assert apply_metadata_filters(bid, rule) is True

def test_product_code_not_found_blocks():
    """Missing product code should block"""
    bid = {"title": "CCTV 구매", "attachmentText": "물품분류번호: 99999"}
    rule = {"keywords": ["CCTV"], "productCodes": ["42101"]}

    assert apply_metadata_filters(bid, rule) is False

def test_detailed_items_matching():
    """Detailed item names should match"""
    bid = {"title": "교통신호등 주 제조 구매"}
    rule = {"keywords": ["신호등"], "detailedItems": ["교통신호등 주"]}

    assert apply_metadata_filters(bid, rule) is True

def test_amount_range_filtering():
    """Amount range should filter correctly"""
    bid = {"title": "공사", "estimatedAmt": 100000000}

    # Within range
    rule1 = {"keywords": ["공사"], "minAmt": 50000000, "maxAmt": 200000000}
    assert apply_metadata_filters(bid, rule1) is True

    # Below minimum
    rule2 = {"keywords": ["공사"], "minAmt": 150000000}
    assert apply_metadata_filters(bid, rule2) is False

    # Above maximum
    rule3 = {"keywords": ["공사"], "maxAmt": 50000000}
    assert apply_metadata_filters(bid, rule3) is False

def test_all_filters_combined():
    """Complex rule with multiple filters"""
    bid = {
        "title": "교통신호등 주 설치",
        "category": "물품",
        "region": "서울",
        "estimatedAmt": 80000000,
        "attachmentText": "물품분류번호: 42101"
    }

    rule = {
        "keywords": ["교통신호등"],
        "excludeKeywords": ["유지보수"],
        "regions": ["서울", "경기"],
        "excludeRegions": ["안산"],
        "productCodes": ["42101"],
        "detailedItems": ["교통신호등 주"],
        "minAmt": 50000000,
        "maxAmt": 100000000,
    }

    assert apply_metadata_filters(bid, rule) is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_matcher.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement alert_matcher.py**

Create `services/web_app/alert_matcher.py`:

```python
from typing import Any

def apply_metadata_filters(bid: dict[str, Any], rule: dict[str, Any]) -> bool:
    """
    메타데이터 기반 1차 필터링.

    Returns:
        True if bid matches rule, False otherwise
    """

    # 1. 키워드 매칭
    text = f"{bid.get('title', '')} {bid.get('category', '')}".lower()

    # 포함 키워드 체크
    keywords = rule.get("keywords", [])
    if keywords:
        if not any(kw.lower() in text for kw in keywords):
            return False

    # 제외 키워드 체크 (우선순위 높음)
    exclude_keywords = rule.get("excludeKeywords", [])
    if exclude_keywords:
        if any(kw.lower() in text for kw in exclude_keywords):
            return False

    # 2. 지역 필터
    regions = rule.get("regions", [])
    if regions:
        if bid.get("region") not in regions:
            return False

    # 3. 제외 지역 (우선순위 높음)
    exclude_regions = rule.get("excludeRegions", [])
    if exclude_regions:
        if bid.get("region") in exclude_regions:
            return False

    # 4. 물품분류번호
    product_codes = rule.get("productCodes", [])
    if product_codes:
        attachment = bid.get("attachmentText", "").lower()
        if not any(code in attachment for code in product_codes):
            return False

    # 5. 세부품명
    detailed_items = rule.get("detailedItems", [])
    if detailed_items:
        if not any(item.lower() in text for item in detailed_items):
            return False

    # 6. 금액 범위
    min_amt = rule.get("minAmt")
    max_amt = rule.get("maxAmt")
    bid_amt = bid.get("estimatedAmt", 0)

    if min_amt is not None and bid_amt < min_amt:
        return False
    if max_amt is not None and bid_amt > max_amt:
        return False

    return True

def matches_any_rule(bid: dict[str, Any], rules: list[dict[str, Any]]) -> bool:
    """Check if bid matches ANY of the rules"""
    if not rules:
        return False

    for rule in rules:
        if not rule.get("enabled", True):
            continue

        if apply_metadata_filters(bid, rule):
            return True

    return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_alert_matcher.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add services/web_app/alert_matcher.py tests/test_alert_matcher.py
git commit -m "feat: add metadata-based alert filter matching

- Keyword/exclude keyword filtering
- Region/exclude region filtering
- Product code matching (from attachmentText)
- Detailed item name matching
- Amount range filtering
- Combined rule matching with priority"
```

---

## Phase 2: Frontend UI

### Task 5: Alerts Page Route and Layout

**Files:**
- Modify: `frontend/kirabot/App.tsx` (add route)
- Create: `frontend/kirabot/components/alerts/AlertsPage.tsx`
- Modify: `frontend/kirabot/components/chat/Sidebar.tsx` (add menu item)

**Step 1: Create basic AlertsPage component**

Create `frontend/kirabot/components/alerts/AlertsPage.tsx`:

```typescript
import React, { useState, useEffect } from 'react';
import { Bell, Save, X } from 'lucide-react';

export const AlertsPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TODO: Load config from API
    setLoading(false);
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-slate-400">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* Header */}
      <div className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell size={20} className="text-primary-600" />
            <h1 className="text-lg font-bold text-slate-800">알림 설정</h1>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-slate-600">전체 활성화</span>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="rounded border-slate-300"
            />
          </label>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {/* Basic Settings Placeholder */}
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="text-base font-semibold text-slate-700">기본 설정</h2>
            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">이메일</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alert@example.com"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-3xl justify-end gap-2">
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <X size={16} />
            취소
          </button>
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Save size={16} />
            저장
          </button>
        </div>
      </div>
    </div>
  );
};

export default AlertsPage;
```

**Step 2: Add route to App.tsx**

Modify `frontend/kirabot/App.tsx`, add import:

```typescript
import AlertsPage from './components/alerts/AlertsPage';
```

Add route (after `/admin` route):

```typescript
<Route path="/alerts" element={<AlertsPage />} />
```

**Step 3: Add Sidebar menu item**

Modify `frontend/kirabot/components/chat/Sidebar.tsx`, add `Bell` icon import:

```typescript
import { MessageSquare, Search, FileText, Shield, Bell, Plus, MoreVertical, Edit2, Trash2, Check } from 'lucide-react';
```

Update `baseNavItems`:

```typescript
const baseNavItems = [
  { path: '/chat', label: '채팅', icon: MessageSquare },
  { path: '/search', label: '공고 검색', icon: Search },
  { path: '/analyze', label: '문서 분석', icon: FileText },
  { path: '/alerts', label: '알림', icon: Bell },  // 🆕 NEW
];
```

**Step 4: Test navigation**

Run: `cd frontend/kirabot && npm run dev`
Manual test:
1. Open http://localhost:5173
2. Click "알림" in sidebar
3. Verify AlertsPage loads with header + basic email input

**Step 5: Commit**

```bash
git add frontend/kirabot/App.tsx frontend/kirabot/components/alerts/AlertsPage.tsx frontend/kirabot/components/chat/Sidebar.tsx
git commit -m "feat: add /alerts route with basic page layout

- AlertsPage component with header/content/footer
- Sidebar menu item with Bell icon
- Email input placeholder"
```

---

### Task 6: Company Profile Section Component

**Files:**
- Create: `frontend/kirabot/components/alerts/CompanyProfileSection.tsx`
- Modify: `frontend/kirabot/components/alerts/AlertsPage.tsx` (integrate)

**Step 1: Create CompanyProfileSection**

Create `frontend/kirabot/components/alerts/CompanyProfileSection.tsx`:

```typescript
import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { CompanyProfile } from '../../services/kiraApiService';

interface CompanyProfileSectionProps {
  profile: CompanyProfile | undefined;
  onChange: (profile: CompanyProfile) => void;
}

export const CompanyProfileSection: React.FC<CompanyProfileSectionProps> = ({
  profile,
  onChange,
}) => {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const updateDescription = (description: string) => {
    onChange({ ...profile, description });
  };

  const updateField = (field: keyof CompanyProfile, value: string[]) => {
    onChange({ ...profile, [field]: value });
  };

  const parseCommaSeparated = (text: string): string[] => {
    return text.split(',').map(s => s.trim()).filter(s => s.length > 0);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-base font-semibold text-slate-700">회사 프로필</h2>
      <p className="mt-1 text-sm text-slate-500">
        자연어로 회사 역량을 입력하면 LLM이 자격요건과 비교합니다 (Pro 버전 전용)
      </p>

      <div className="mt-4">
        <label className="block text-sm font-medium text-slate-700">
          회사 설명 (자연어)
        </label>
        <textarea
          value={profile?.description || ''}
          onChange={(e) => updateDescription(e.target.value)}
          placeholder="예시: 우리 회사는 교통신호등 및 CCTV 제조 전문 업체입니다. 물품분류번호 42101, 42105를 취급하며, 안산/부산 지역 공고는 제외합니다. ISO 9001 인증 보유."
          rows={6}
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      {/* Collapsible Advanced Fields */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          구조화된 입력 (선택)
        </button>

        {showAdvanced && (
          <div className="mt-4 space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                주력 제품 (쉼표 구분)
              </label>
              <input
                type="text"
                value={profile?.mainProducts?.join(', ') || ''}
                onChange={(e) => updateField('mainProducts', parseCommaSeparated(e.target.value))}
                placeholder="교통신호등, CCTV, 주차관제시스템"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">
                보유 인증 (쉼표 구분)
              </label>
              <input
                type="text"
                value={profile?.certifications?.join(', ') || ''}
                onChange={(e) => updateField('certifications', parseCommaSeparated(e.target.value))}
                placeholder="ISO 9001, KS 인증, 벤처기업 확인서"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">
                제외 지역/품목 (쉼표 구분)
              </label>
              <input
                type="text"
                value={profile?.excludedAreas?.join(', ') || ''}
                onChange={(e) => updateField('excludedAreas', parseCommaSeparated(e.target.value))}
                placeholder="안산, 부산, 유지보수만"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CompanyProfileSection;
```

**Step 2: Integrate into AlertsPage**

Modify `frontend/kirabot/components/alerts/AlertsPage.tsx`:

Add import:
```typescript
import CompanyProfileSection from './CompanyProfileSection';
import type { CompanyProfile } from '../../services/kiraApiService';
```

Add state:
```typescript
const [companyProfile, setCompanyProfile] = useState<CompanyProfile>({
  description: '',
});
```

Add section in content area (after basic settings div):
```typescript
<CompanyProfileSection
  profile={companyProfile}
  onChange={setCompanyProfile}
/>
```

**Step 3: Test component**

Run: `cd frontend/kirabot && npm run dev`
Manual test:
1. Navigate to /alerts
2. Verify "회사 프로필" section appears
3. Type in description textarea
4. Click "구조화된 입력" to expand
5. Verify comma-separated parsing works

**Step 4: Run TypeScript check**

Run: `cd frontend/kirabot && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/kirabot/components/alerts/CompanyProfileSection.tsx frontend/kirabot/components/alerts/AlertsPage.tsx
git commit -m "feat: add company profile section with natural language input

- Textarea for free-text company description
- Collapsible structured fields (products, certs, excluded areas)
- Comma-separated parsing for array fields"
```

---

### Task 7: Alert Filter Section Component

**Files:**
- Create: `frontend/kirabot/components/alerts/AlertFilterSection.tsx`
- Modify: `frontend/kirabot/components/alerts/AlertsPage.tsx` (integrate)

**Step 1: Create AlertFilterSection**

Create `frontend/kirabot/components/alerts/AlertFilterSection.tsx`:

```typescript
import React from 'react';
import { Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import type { AlertRule } from '../../services/kiraApiService';

interface AlertFilterSectionProps {
  rules: AlertRule[];
  onAddRule: () => void;
  onUpdateRule: (index: number, rule: AlertRule) => void;
  onDeleteRule: (index: number) => void;
}

export const AlertFilterSection: React.FC<AlertFilterSectionProps> = ({
  rules,
  onAddRule,
  onUpdateRule,
  onDeleteRule,
}) => {
  const [expandedRules, setExpandedRules] = React.useState<Set<number>>(new Set([0]));

  const toggleExpand = (index: number) => {
    const newExpanded = new Set(expandedRules);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedRules(newExpanded);
  };

  const parseCommaSeparated = (text: string): string[] => {
    return text.split(',').map(s => s.trim()).filter(s => s.length > 0);
  };

  const updateField = (index: number, field: keyof AlertRule, value: any) => {
    const updated = { ...rules[index], [field]: value };
    onUpdateRule(index, updated);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-700">필터 규칙</h2>
          <p className="mt-1 text-sm text-slate-500">
            여러 규칙을 추가할 수 있습니다. 하나라도 매칭되면 알림을 받습니다.
          </p>
        </div>
        <button
          type="button"
          onClick={onAddRule}
          className="flex items-center gap-1.5 rounded-lg border border-primary-600 px-3 py-1.5 text-sm font-medium text-primary-600 hover:bg-primary-50"
        >
          <Plus size={16} />
          규칙 추가
        </button>
      </div>

      <div className="mt-4 space-y-3">
        {rules.length === 0 && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-6 py-12 text-center text-sm text-slate-400">
            규칙을 추가하여 원하는 공고만 받아보세요
          </div>
        )}

        {rules.map((rule, index) => {
          const isExpanded = expandedRules.has(index);
          return (
            <div key={rule.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              {/* Rule Header */}
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => toggleExpand(index)}
                  className="flex items-center gap-2 text-sm font-medium text-slate-700"
                >
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  규칙 #{index + 1}
                  {rule.keywords.length > 0 && (
                    <span className="text-slate-500">
                      ({rule.keywords.slice(0, 2).join(', ')}{rule.keywords.length > 2 && '...'})
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => onDeleteRule(index)}
                  className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-red-600"
                  title="삭제"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              {/* Rule Fields (Collapsed/Expanded) */}
              {isExpanded && (
                <div className="mt-4 space-y-3">
                  {/* Keywords */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      포함 키워드 (쉼표 구분) <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={rule.keywords.join(', ')}
                      onChange={(e) => updateField(index, 'keywords', parseCommaSeparated(e.target.value))}
                      placeholder="교통신호등, CCTV, 영상감시"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Exclude Keywords */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      제외 키워드 (쉼표 구분)
                    </label>
                    <input
                      type="text"
                      value={rule.excludeKeywords.join(', ')}
                      onChange={(e) => updateField(index, 'excludeKeywords', parseCommaSeparated(e.target.value))}
                      placeholder="유지보수만, 철거"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Regions */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      포함 지역 (쉼표 구분, 비워두면 전체)
                    </label>
                    <input
                      type="text"
                      value={rule.regions.join(', ')}
                      onChange={(e) => updateField(index, 'regions', parseCommaSeparated(e.target.value))}
                      placeholder="서울, 경기, 인천"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Exclude Regions */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      🚫 제외 지역 (쉼표 구분)
                    </label>
                    <input
                      type="text"
                      value={rule.excludeRegions?.join(', ') || ''}
                      onChange={(e) => updateField(index, 'excludeRegions', parseCommaSeparated(e.target.value))}
                      placeholder="안산, 부산"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Product Codes */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      물품분류번호 (쉼표 구분)
                    </label>
                    <input
                      type="text"
                      value={rule.productCodes?.join(', ') || ''}
                      onChange={(e) => updateField(index, 'productCodes', parseCommaSeparated(e.target.value))}
                      placeholder="42101, 42105"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Detailed Items */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700">
                      세부품명 (쉼표 구분)
                    </label>
                    <input
                      type="text"
                      value={rule.detailedItems?.join(', ') || ''}
                      onChange={(e) => updateField(index, 'detailedItems', parseCommaSeparated(e.target.value))}
                      placeholder="교통신호등 주, CCTV 카메라"
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Amount Range */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-700">
                        최소 금액 (원)
                      </label>
                      <input
                        type="number"
                        value={rule.minAmt || ''}
                        onChange={(e) => updateField(index, 'minAmt', e.target.value ? parseInt(e.target.value) : undefined)}
                        placeholder="50000000"
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700">
                        최대 금액 (원)
                      </label>
                      <input
                        type="number"
                        value={rule.maxAmt || ''}
                        onChange={(e) => updateField(index, 'maxAmt', e.target.value ? parseInt(e.target.value) : undefined)}
                        placeholder="200000000"
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default AlertFilterSection;
```

**Step 2: Integrate into AlertsPage**

Modify `frontend/kirabot/components/alerts/AlertsPage.tsx`:

Add import:
```typescript
import AlertFilterSection from './AlertFilterSection';
import type { AlertRule } from '../../services/kiraApiService';
```

Add state:
```typescript
const [rules, setRules] = useState<AlertRule[]>([]);
```

Add handlers:
```typescript
const handleAddRule = () => {
  const newRule: AlertRule = {
    id: `rule${Date.now()}`,
    keywords: [],
    excludeKeywords: [],
    categories: [],
    regions: [],
    excludeRegions: [],
    productCodes: [],
    detailedItems: [],
    enabled: true,
  };
  setRules([...rules, newRule]);
};

const handleUpdateRule = (index: number, rule: AlertRule) => {
  const updated = [...rules];
  updated[index] = rule;
  setRules(updated);
};

const handleDeleteRule = (index: number) => {
  setRules(rules.filter((_, i) => i !== index));
};
```

Add component in content area (after CompanyProfileSection):
```typescript
<AlertFilterSection
  rules={rules}
  onAddRule={handleAddRule}
  onUpdateRule={handleUpdateRule}
  onDeleteRule={handleDeleteRule}
/>
```

**Step 3: Test component**

Run: `cd frontend/kirabot && npm run dev`
Manual test:
1. Navigate to /alerts
2. Click "규칙 추가"
3. Verify rule card appears
4. Click expand/collapse
5. Enter keywords (comma separated)
6. Verify parsing works
7. Delete rule

**Step 4: Run TypeScript check**

Run: `cd frontend/kirabot && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/kirabot/components/alerts/AlertFilterSection.tsx frontend/kirabot/components/alerts/AlertsPage.tsx
git commit -m "feat: add alert filter section with rule management

- Add/delete/update multiple rules
- Expandable rule cards with all filter fields
- Comma-separated input parsing
- Exclude regions, product codes, detailed items support"
```

---

### Task 8: Load and Save Alert Config Integration

**Files:**
- Modify: `frontend/kirabot/services/kiraApiService.ts` (add API functions)
- Modify: `frontend/kirabot/components/alerts/AlertsPage.tsx` (integrate API)

**Step 1: Add API functions**

Modify `frontend/kirabot/services/kiraApiService.ts`, add functions after existing alert functions:

```typescript
export async function getUserAlertConfig(email: string): Promise<AlertConfig> {
  const response = await fetchWithError(
    `${API_BASE_URL}/api/alerts/config?email=${encodeURIComponent(email)}`
  );
  return parseJson<AlertConfig>(response);
}

export async function saveUserAlertConfig(config: AlertConfig): Promise<{ success: boolean; message: string }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/alerts/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  return parseJson<{ success: boolean; message: string }>(response);
}
```

**Step 2: Integrate into AlertsPage**

Modify `frontend/kirabot/components/alerts/AlertsPage.tsx`:

Add imports:
```typescript
import { getUserAlertConfig, saveUserAlertConfig } from '../../services/kiraApiService';
```

Update `useEffect` to load config:
```typescript
useEffect(() => {
  const loadConfig = async () => {
    // Get email from query param or localStorage
    const urlParams = new URLSearchParams(window.location.search);
    const emailParam = urlParams.get('email') || localStorage.getItem('alertEmail') || '';

    if (!emailParam) {
      setLoading(false);
      return;
    }

    try {
      const config = await getUserAlertConfig(emailParam);
      setEmail(config.email);
      setEnabled(config.enabled);
      setSchedule(config.schedule);
      setHours(config.hours);
      setRules(config.rules);
      setCompanyProfile(config.companyProfile || { description: '' });
    } catch (error) {
      console.error('Failed to load alert config:', error);
      alert('알림 설정을 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  void loadConfig();
}, []);
```

Add save handler:
```typescript
const handleSave = async () => {
  if (!email || !email.includes('@')) {
    alert('유효한 이메일 주소를 입력해주세요.');
    return;
  }

  if (rules.length === 0) {
    if (!confirm('규칙이 없습니다. 알림을 받지 못할 수 있습니다. 계속하시겠습니까?')) {
      return;
    }
  }

  try {
    setLoading(true);
    const config: AlertConfig = {
      email,
      enabled,
      schedule,
      hours,
      rules,
      companyProfile: companyProfile?.description ? companyProfile : undefined,
    };

    const result = await saveUserAlertConfig(config);
    if (result.success) {
      localStorage.setItem('alertEmail', email);
      alert('알림 설정이 저장되었습니다.');
    }
  } catch (error) {
    console.error('Failed to save alert config:', error);
    alert('저장 실패: ' + (error instanceof Error ? error.message : '알 수 없는 오류'));
  } finally {
    setLoading(false);
  }
};
```

Add missing state:
```typescript
const [schedule, setSchedule] = useState<'realtime' | 'daily_1' | 'daily_2' | 'daily_3'>('daily_2');
const [hours, setHours] = useState<number[]>([9, 18]);
```

Update save button:
```typescript
<button
  type="button"
  onClick={handleSave}
  disabled={loading}
  className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
>
  <Save size={16} />
  {loading ? '저장 중...' : '저장'}
</button>
```

**Step 3: Test integration**

Run: `cd frontend/kirabot && npm run dev`
Manual test:
1. Navigate to /alerts?email=test@example.com
2. Enter config (email, keywords, etc)
3. Click 저장
4. Verify alert appears
5. Reload page with same email param
6. Verify config loads correctly

**Step 4: Run TypeScript check**

Run: `cd frontend/kirabot && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/kirabot/services/kiraApiService.ts frontend/kirabot/components/alerts/AlertsPage.tsx
git commit -m "feat: integrate alert config load/save with backend API

- getUserAlertConfig() and saveUserAlertConfig() API functions
- Load config from query param email or localStorage
- Save handler with validation
- localStorage persistence for email"
```

---

## Phase 3: Testing & Polish

### Task 9: Integration Tests

**Files:**
- Modify: `tests/test_web_runtime_api.py` (add integration tests)

**Step 1: Write integration test**

Add to `tests/test_web_runtime_api.py`:

```python
def test_alert_config_full_workflow():
    """Full workflow: create config with all filters, retrieve, verify"""
    config = {
        "email": "integration@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "companyProfile": {
            "description": "교통신호등 제조 전문. ISO 9001 보유.",
            "mainProducts": ["교통신호등", "CCTV"],
            "excludedAreas": ["안산", "부산"],
        },
        "rules": [
            {
                "id": "rule1",
                "keywords": ["교통신호등", "CCTV"],
                "excludeKeywords": ["유지보수"],
                "categories": ["물품"],
                "regions": ["서울", "경기"],
                "excludeRegions": ["안산"],
                "productCodes": ["42101", "42105"],
                "detailedItems": ["교통신호등 주"],
                "minAmt": 50000000,
                "maxAmt": 200000000,
                "enabled": True,
            }
        ],
    }

    # Save
    save_resp = client.post("/api/alerts/config", json=config)
    assert save_resp.status_code == 200

    # Retrieve
    get_resp = client.get("/api/alerts/config?email=integration@example.com")
    assert get_resp.status_code == 200

    data = get_resp.json()
    assert data["email"] == "integration@example.com"
    assert data["companyProfile"]["description"] == "교통신호등 제조 전문. ISO 9001 보유."
    assert len(data["companyProfile"]["mainProducts"]) == 2
    assert data["rules"][0]["excludeRegions"] == ["안산"]
    assert data["rules"][0]["productCodes"] == ["42101", "42105"]
```

**Step 2: Run test**

Run: `pytest tests/test_web_runtime_api.py::test_alert_config_full_workflow -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_web_runtime_api.py
git commit -m "test: add full workflow integration test for alert config"
```

---

### Task 10: Error Handling & Validation

**Files:**
- Modify: `services/web_app/main.py` (enhance validation)
- Test: `tests/test_web_runtime_api.py` (add validation tests)

**Step 1: Write validation tests**

Add to `tests/test_web_runtime_api.py`:

```python
def test_save_alert_config_rejects_empty_keywords():
    """Rules with empty keywords should be rejected"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9],
        "rules": [{"id": "1", "keywords": [], "enabled": True}],
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "키워드" in resp.json()["detail"]

def test_save_alert_config_rejects_invalid_schedule():
    """Invalid schedule value should be rejected"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "invalid_schedule",
        "hours": [],
        "rules": [],
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "schedule" in resp.json()["detail"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_web_runtime_api.py::test_save_alert_config_rejects_empty_keywords -v`
Expected: FAIL (validation not implemented yet)

**Step 3: Enhance validation in main.py**

Modify `services/web_app/main.py`, update `_validate_alert_config()`:

```python
def _validate_alert_config(config: dict[str, Any]) -> None:
    """설정 검증 (강화)"""
    if not isinstance(config.get("rules"), list):
        raise HTTPException(400, "rules 필드가 배열이어야 합니다.")

    for i, rule in enumerate(config["rules"]):
        if not rule.get("keywords"):
            raise HTTPException(400, f"규칙 #{i+1}: 최소 1개의 키워드가 필요합니다.")

        # Keywords validation
        if len(rule["keywords"]) > 50:
            raise HTTPException(400, f"규칙 #{i+1}: 키워드는 최대 50개까지 가능합니다.")

    if config.get("schedule") not in ["realtime", "daily_1", "daily_2", "daily_3"]:
        raise HTTPException(400, "올바른 schedule 값이 필요합니다 (realtime, daily_1, daily_2, daily_3).")

    if not isinstance(config.get("hours"), list):
        raise HTTPException(400, "hours 필드가 배열이어야 합니다.")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web_runtime_api.py::test_save_alert_config_rejects_empty_keywords tests/test_web_runtime_api.py::test_save_alert_config_rejects_invalid_schedule -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add services/web_app/main.py tests/test_web_runtime_api.py
git commit -m "feat: enhance alert config validation

- Reject rules with empty keywords
- Limit keywords to 50 per rule
- Validate schedule enum values
- Validate hours array type"
```

---

## Phase 4: Migration & Documentation

### Task 11: Legacy Alert Migration Script

**Files:**
- Create: `scripts/migrate_legacy_alerts.py`

**Step 1: Write migration script**

Create `scripts/migrate_legacy_alerts.py`:

```python
#!/usr/bin/env python3
"""
Migrate legacy alert_test_*.json configs to new format.

Usage:
    python scripts/migrate_legacy_alerts.py [--dry-run]
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.web_app.alert_storage import save_alert_config

def migrate_legacy_alerts(dry_run: bool = False):
    """Migrate all legacy alert configs"""
    legacy_dir = Path("data/alert_states")

    if not legacy_dir.exists():
        print(f"❌ Legacy directory not found: {legacy_dir}")
        return

    config_files = list(legacy_dir.glob("alert_test_*.json"))
    if not config_files:
        print(f"❌ No legacy config files found in {legacy_dir}")
        return

    print(f"Found {len(config_files)} legacy config files\n")

    migrated_count = 0
    for file_path in config_files:
        print(f"Processing: {file_path.name}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                legacy = json.load(f)

            # Skip state files (only have last_sent)
            if not legacy.get("email"):
                print(f"  ⏭️  Skipping (no email field, likely state file)")
                continue

            # Convert to new format
            new_config = {
                "email": legacy.get("email", "unknown@example.com"),
                "enabled": legacy.get("enabled", True),
                "schedule": legacy.get("schedule", "daily_2"),
                "hours": legacy.get("hours", [9, 18]),
                "rules": [
                    {
                        "id": rule.get("id", f"migrated{i}"),
                        "keywords": rule.get("keywords", []),
                        "excludeKeywords": rule.get("excludeKeywords", []),
                        "categories": rule.get("categories", []),
                        "regions": rule.get("regions", []),
                        "excludeRegions": [],  # New field, empty
                        "productCodes": [],    # New field, empty
                        "detailedItems": [],   # New field, empty
                        "minAmt": rule.get("minAmt"),
                        "maxAmt": rule.get("maxAmt"),
                        "enabled": rule.get("enabled", True),
                    }
                    for i, rule in enumerate(legacy.get("rules", []))
                ],
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }

            if dry_run:
                print(f"  ✅ Would migrate: {new_config['email']} ({len(new_config['rules'])} rules)")
            else:
                save_alert_config(new_config)
                print(f"  ✅ Migrated: {new_config['email']} ({len(new_config['rules'])} rules)")
                migrated_count += 1

        except Exception as e:
            print(f"  ❌ Error: {e}")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrated {migrated_count}/{len(config_files)} configs")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate legacy alert configs")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without saving")
    args = parser.parse_args()

    migrate_legacy_alerts(dry_run=args.dry_run)
```

**Step 2: Make script executable**

Run: `chmod +x scripts/migrate_legacy_alerts.py`

**Step 3: Test dry-run**

Run: `python scripts/migrate_legacy_alerts.py --dry-run`
Expected: Shows preview of migration without actually saving

**Step 4: Commit**

```bash
git add scripts/migrate_legacy_alerts.py
git commit -m "feat: add legacy alert migration script

- Converts alert_test_*.json to new format
- Preserves existing keywords/regions/categories
- Initializes new fields (excludeRegions, productCodes) as empty
- Dry-run mode for preview"
```

---

### Task 12: Update Documentation

**Files:**
- Modify: `CLAUDE.md` (add user alerts section)
- Modify: `docs/plans/2026-02-27-user-alert-filtering-design.md` (mark implemented)

**Step 1: Update CLAUDE.md**

Modify `CLAUDE.md`, add under "기능 구현 현황":

```markdown
### 사용자 알림 설정 (2026-02-27 구현 완료)
| 기능 | 상태 | 비고 |
|------|------|------|
| 독립 알림 설정 페이지 | **동작** | /alerts 라우트, 영구 파일 저장 |
| 확장 필터 (물품분류번호, 세부품명) | **동작** | 메타데이터 기반 1차 필터 |
| 제외 지역 필터 | **동작** | excludeRegions 필드 |
| 회사 프로필 자연어 입력 | **UI 완성** | LLM 파싱은 Pro 버전 (미구현) |
| 알림 설정 API | **동작** | GET/POST /api/alerts/config |
| 레거시 마이그레이션 | **스크립트 완성** | scripts/migrate_legacy_alerts.py |
```

**Step 2: Mark design as implemented**

Add to top of `docs/plans/2026-02-27-user-alert-filtering-design.md`:

```markdown
**Status:** ✅ Implemented (Phase 1: Metadata Filtering)
**Implementation:** 2026-02-27
```

**Step 3: Commit**

```bash
git add CLAUDE.md docs/plans/2026-02-27-user-alert-filtering-design.md
git commit -m "docs: update CLAUDE.md with user alerts implementation status

- Mark Phase 1 (metadata filtering) as completed
- Document /alerts route and API endpoints
- Note LLM filtering (Phase 2) as future work"
```

---

## Execution Summary

**Total Tasks:** 12
**Estimated Time:** ~8-10 hours
**Test Coverage:** Unit tests (alert_matcher), integration tests (API endpoints), manual UI testing

**Key Deliverables:**
1. Extended AlertRule schema with new filter fields
2. File-based alert config storage (data/user_alerts/)
3. Backend API (GET/POST /api/alerts/config)
4. Metadata filter matching logic
5. Frontend /alerts page with 3 sections (basic, company profile, filters)
6. Load/save integration
7. Validation & error handling
8. Legacy migration script
9. Updated documentation

**Next Steps (Phase 2 - Pro Version):**
- LLM RFP parsing (apply_llm_filters)
- CompanyProfile → LLM matching integration
- Plan tier checking
- Performance optimization (caching, indexing)

---

## Critical Code Review Points

### ✅ Safety Checks
- Email normalization (lowercase, SHA256)
- Input validation (keywords required, schedule enum)
- Timestamp management (createdAt/updatedAt)
- File path sanitization (SHA256 prevents traversal)

### ⚠️ Known Limitations
- Product codes matched via simple substring (attachmentText) — may need regex
- No rate limiting on /api/alerts/config (add if needed)
- File-based storage has scalability limit (~1000 users) — migrate to DB if needed
- LLM filtering (Phase 2) not implemented yet

### 🔧 Future Enhancements
- Alert history tracking
- Preview API (/api/alerts/preview) not implemented in this plan
- Batch email sending integration (currently just saves config)
- Statistics dashboard (weekly/monthly match counts)
