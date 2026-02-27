# 사용자 알림 설정 고도화 설계

**Date:** 2026-02-27
**Status:** Design
**Goal:** 일반 사용자가 회사 프로필 기반으로 세부 필터링된 입찰 공고 알림을 직접 설정할 수 있도록 개선

---

## 배경

현재 알림 시스템은 관리자만 설정 가능하며, 필터링이 단순함 (keywords, regions). 사용자가 원하는 세부 조건:

- **물품분류번호**: 특정 코드만 취급 (예: 42101, 42105)
- **세부품명**: 정확한 품목명 매칭 (예: "교통신호등 주", "CCTV")
- **제외 지역**: 특정 지역 공고 차단 (예: 안산, 부산)
- **발주처 소재지**: 발주처가 특정 지역에 있으면 제외
- **회사 프로필**: 자연어로 회사 역량 입력 → LLM이 자격요건과 비교 (Pro 버전)

**요구사항:**
1. 일반 사용자가 직접 설정 가능한 독립 UI
2. 영구 저장 (브라우저 닫아도 유지)
3. 하이브리드 필터링: 메타데이터 1차 (무료) + LLM 2차 (Pro, 향후)

---

## 아키텍처

### 전체 구조

```
frontend/kirabot/
  App.tsx                         ← /alerts 라우트 추가
  components/alerts/
    AlertsPage.tsx                ← 알림 설정 페이지 (메인)
    AlertBasicSettings.tsx        ← 이메일, 알림 빈도
    AlertFilterSection.tsx        ← 키워드, 지역, 금액 필터
    CompanyProfileSection.tsx     ← 회사 프로필 (자연어 + 구조화)
    FilterPreview.tsx             ← 필터 테스트 결과 미리보기
  components/chat/Sidebar.tsx     ← "🔔 알림" 메뉴 추가

services/web_app/main.py
  GET  /api/alerts/config?email=  ← 알림 설정 조회
  POST /api/alerts/config         ← 알림 설정 저장
  POST /api/alerts/preview        ← 필터 미리보기 (최근 공고 몇 건 매칭?)

services/web_app/alert_matcher.py (신규)
  match_bid_notice()              ← BidNotice가 AlertRule 매칭하는지 판단
  apply_metadata_filters()        ← Stage 1: 메타데이터 필터
  apply_llm_filters()             ← Stage 2: LLM 자격요건 파싱 (Pro)

data/user_alerts/
  {sha256(email)}.json            ← 사용자별 설정 영구 저장
```

---

## 데이터 모델

### AlertConfig (확장)

기존 필드 유지 + 새 필드 추가:

```typescript
interface AlertRule {
  // 기존
  id: string;
  keywords: string[];              // 포함 키워드 (title/category)
  excludeKeywords: string[];       // 제외 키워드
  categories: string[];            // 업무구분 (용역, 물품, 공사 등)
  regions: string[];               // 포함 지역
  minAmt?: number;                 // 최소 금액
  maxAmt?: number;                 // 최대 금액
  enabled: boolean;

  // 🆕 신규
  productCodes?: string[];         // 물품분류번호 (예: "42101", "42105")
  detailedItems?: string[];        // 세부품명 키워드 (예: "교통신호등 주")
  excludeRegions?: string[];       // 제외 지역 (예: ["안산", "부산"])
  excludeContractorLocations?: string[];  // 제외 발주처 소재지
}

interface CompanyProfile {
  description: string;             // 자연어 회사 설명 (LLM 파싱용)
  businessTypes?: string[];        // 주요 업종
  certifications?: string[];       // 보유 인증
  mainProducts?: string[];         // 주력 제품
  excludedAreas?: string[];        // 절대 배제 항목
}

interface AlertConfig {
  email: string;                   // 사용자 식별자 (필수)
  enabled: boolean;
  schedule: 'realtime' | 'daily_1' | 'daily_2' | 'daily_3';
  hours: number[];
  rules: AlertRule[];
  companyProfile?: CompanyProfile; // 🆕 회사 프로필
  createdAt: string;
  updatedAt: string;
}
```

### 저장 경로

- **파일명**: `data/user_alerts/{sha256(email)}.json`
- **이유**: 이메일 해시로 식별, 파일 시스템 기반 (빠른 구현, DB 불필요)
- **예시**: `user@example.com` → `data/user_alerts/b4c7a9...f2e.json`

---

## UI 컴포넌트 설계

### 1. AlertsPage (메인 페이지)

**라우트:** `/alerts`
**레이아웃:** 3단 섹션 구조

```tsx
<AlertsPage>
  <Header>
    <h1>알림 설정</h1>
    <ToggleSwitch checked={enabled} onChange={...} />  {/* 전체 활성화 */}
  </Header>

  <AlertBasicSettings
    email={email}
    schedule={schedule}
    hours={hours}
    onChange={...}
  />

  <CompanyProfileSection
    profile={companyProfile}
    onChange={...}
  />

  <AlertFilterSection
    rules={rules}
    onAddRule={...}
    onEditRule={...}
    onDeleteRule={...}
  />

  <FilterPreview
    rules={rules}
    onTest={() => api.previewAlertFilters(...)}
  />

  <Footer>
    <Button variant="outline" onClick={onCancel}>취소</Button>
    <Button variant="primary" onClick={onSave}>저장</Button>
  </Footer>
</AlertsPage>
```

### 2. CompanyProfileSection

**입력 방식:** 자연어 textarea + 구조화된 필드 (선택)

```tsx
<CompanyProfileSection>
  <Label>회사 프로필 (자연어로 입력하세요)</Label>
  <Textarea
    placeholder="예시: 우리 회사는 교통신호등 및 CCTV 제조 전문 업체입니다. 물품분류번호 42101, 42105를 취급하며, 안산/부산 지역 공고는 제외합니다. ISO 9001 인증 보유."
    value={profile.description}
    onChange={...}
    rows={6}
  />

  <Collapsible label="구조화된 입력 (선택)">
    <Input label="주력 제품" placeholder="교통신호등, CCTV" />
    <Input label="보유 인증" placeholder="ISO 9001, KS 인증" />
    <Input label="제외 지역" placeholder="안산, 부산" />
  </Collapsible>
</CompanyProfileSection>
```

**자체 리뷰:**
- ✅ 자연어 + 구조화 하이브리드 → 사용자 선택권
- ✅ 예시 텍스트로 입력 가이드
- ⚠️ LLM 파싱 정확도 검증 필요 (테스트 케이스 필수)

### 3. AlertFilterSection

**여러 규칙 지원:** 사용자가 규칙을 여러 개 추가 가능

```tsx
<AlertFilterSection>
  {rules.map(rule => (
    <RuleCard key={rule.id}>
      <Input label="포함 키워드" value={rule.keywords.join(', ')} />
      <Input label="제외 키워드" value={rule.excludeKeywords.join(', ')} />
      <MultiSelect label="업무구분" options={['용역', '물품', '공사']} />
      <MultiSelect label="포함 지역" options={regions} />
      <Input label="🚫 제외 지역" placeholder="안산, 부산" />
      <Input label="물품분류번호" placeholder="42101, 42105" />
      <Input label="세부품명" placeholder="교통신호등 주, CCTV" />
      <RangeInput label="금액" min={rule.minAmt} max={rule.maxAmt} />
      <Button variant="danger" onClick={() => onDeleteRule(rule.id)}>삭제</Button>
    </RuleCard>
  ))}
  <Button variant="outline" onClick={onAddRule}>+ 규칙 추가</Button>
</AlertFilterSection>
```

**자체 리뷰:**
- ✅ 여러 규칙 지원 → 복잡한 조건 조합 가능
- ✅ 제외 지역/키워드 필드 명확히 구분
- ⚠️ 너무 많은 필드 → UX 부담. Collapsible로 "고급 필터" 숨기기 고려

### 4. FilterPreview

**실시간 미리보기:** 현재 설정으로 최근 공고 몇 건 매칭되는지 표시

```tsx
<FilterPreview>
  <Button onClick={onTest}>필터 테스트</Button>
  {result && (
    <div>
      <p>최근 100건 중 <strong>{result.matchCount}건</strong> 매칭</p>
      <ul>
        {result.samples.map(bid => (
          <li key={bid.id}>{bid.title} - {bid.region}</li>
        ))}
      </ul>
    </div>
  )}
</FilterPreview>
```

**자체 리뷰:**
- ✅ 사용자가 필터 효과 즉시 확인 가능 → 오설정 방지
- ✅ 샘플 공고 표시 → 신뢰도 증가

---

## Backend API 설계

### 1. GET /api/alerts/config

**목적:** 사용자 알림 설정 조회

**요청:**
```http
GET /api/alerts/config?email=user@example.com
```

**응답:**
```json
{
  "email": "user@example.com",
  "enabled": true,
  "schedule": "daily_2",
  "hours": [9, 18],
  "companyProfile": { ... },
  "rules": [ ... ],
  "createdAt": "2026-02-27T12:00:00Z",
  "updatedAt": "2026-02-27T12:00:00Z"
}
```

**구현:**
```python
@app.get("/api/alerts/config")
def get_alert_config(email: str) -> dict[str, Any]:
    """사용자 알림 설정 조회"""
    if not email or '@' not in email:
        raise HTTPException(400, "유효한 이메일 주소가 필요합니다.")

    file_path = _get_alert_config_path(email)
    if not file_path.exists():
        # 기본 설정 반환
        return _default_alert_config(email)

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _get_alert_config_path(email: str) -> Path:
    email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
    return Path(f"data/user_alerts/{email_hash}.json")
```

**자체 리뷰:**
- ✅ 이메일 소문자 정규화 (case-insensitive)
- ✅ 존재하지 않으면 기본 설정 반환
- ⚠️ 이메일 검증 강화 필요 (정규식 또는 `email-validator` 라이브러리)

---

### 2. POST /api/alerts/config

**목적:** 알림 설정 저장

**요청:**
```json
{
  "email": "user@example.com",
  "enabled": true,
  "schedule": "daily_2",
  "hours": [9, 18],
  "companyProfile": { ... },
  "rules": [ ... ]
}
```

**응답:**
```json
{
  "success": true,
  "message": "알림 설정이 저장되었습니다."
}
```

**구현:**
```python
@app.post("/api/alerts/config")
def save_alert_config(config: dict[str, Any]) -> dict[str, Any]:
    """알림 설정 저장"""
    email = config.get("email")
    if not email or '@' not in email:
        raise HTTPException(400, "유효한 이메일 주소가 필요합니다.")

    # 입력 검증
    _validate_alert_config(config)

    # 타임스탬프 추가
    now = datetime.now(timezone.utc).isoformat()
    config["updatedAt"] = now
    if "createdAt" not in config:
        config["createdAt"] = now

    # 저장
    file_path = _get_alert_config_path(email)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    return {"success": True, "message": "알림 설정이 저장되었습니다."}

def _validate_alert_config(config: dict[str, Any]) -> None:
    """설정 검증"""
    if not isinstance(config.get("rules"), list):
        raise HTTPException(400, "rules 필드가 배열이어야 합니다.")

    for rule in config["rules"]:
        if not rule.get("keywords"):
            raise HTTPException(400, "각 규칙은 최소 1개의 키워드가 필요합니다.")

    if config.get("schedule") not in ["realtime", "daily_1", "daily_2", "daily_3"]:
        raise HTTPException(400, "올바른 schedule 값이 필요합니다.")
```

**자체 리뷰:**
- ✅ 입력 검증 (keywords 필수, schedule 범위 체크)
- ✅ createdAt/updatedAt 타임스탬프 관리
- ✅ 디렉토리 자동 생성 (`mkdir -p`)
- ⚠️ Pydantic 모델로 검증하면 더 깔끔 (향후 개선)

---

### 3. POST /api/alerts/preview

**목적:** 필터 미리보기 (최근 공고 중 매칭 건수)

**요청:**
```json
{
  "rules": [ ... ],
  "limit": 100
}
```

**응답:**
```json
{
  "totalChecked": 100,
  "matchCount": 12,
  "samples": [
    { "id": "...", "title": "교통신호등 설치 공사", "region": "서울" },
    ...
  ]
}
```

**구현:**
```python
@app.post("/api/alerts/preview")
def preview_alert_filters(payload: dict[str, Any]) -> dict[str, Any]:
    """필터 미리보기"""
    rules = payload.get("rules", [])
    limit = min(payload.get("limit", 100), 500)  # 최대 500건

    # 최근 공고 조회 (나라장터 API 또는 DB)
    recent_bids = _fetch_recent_bids(limit)

    # 필터 적용
    matched = []
    for bid in recent_bids:
        if _matches_any_rule(bid, rules):
            matched.append({
                "id": bid["bidNoticeId"],
                "title": bid["bidNtceNm"],
                "region": bid.get("rgstDt", ""),
            })

    return {
        "totalChecked": len(recent_bids),
        "matchCount": len(matched),
        "samples": matched[:10],  # 최대 10건 샘플
    }
```

**자체 리뷰:**
- ✅ limit 상한 제한 (500건) → API 남용 방지
- ✅ 샘플만 반환 (최대 10건) → 응답 크기 제한
- ⚠️ `_fetch_recent_bids()` 캐싱 필요 (나라장터 API 호출 비용)

---

## 필터 매칭 로직 (2단계)

### Stage 1: 메타데이터 필터 (무료, 빠름)

**적용 대상:** BidNotice 필드 (title, category, region, estimatedAmt, attachmentText)

```python
def apply_metadata_filters(bid: dict[str, Any], rule: AlertRule) -> bool:
    """메타데이터 기반 1차 필터링"""

    # 1. 키워드 매칭
    text = f"{bid['title']} {bid.get('category', '')}".lower()

    # 포함 키워드 체크
    if rule.keywords:
        if not any(kw.lower() in text for kw in rule.keywords):
            return False  # 포함 키워드 없으면 탈락

    # 제외 키워드 체크
    if rule.excludeKeywords:
        if any(kw.lower() in text for kw in rule.excludeKeywords):
            return False  # 제외 키워드 있으면 탈락

    # 2. 지역 필터
    if rule.regions:
        if bid.get('region') not in rule.regions:
            return False

    # 🆕 3. 제외 지역
    if rule.excludeRegions:
        if bid.get('region') in rule.excludeRegions:
            return False  # 제외 지역이면 탈락

    # 🆕 4. 물품분류번호 (attachmentText 또는 별도 필드에서)
    if rule.productCodes:
        attachment = bid.get('attachmentText', '').lower()
        if not any(code in attachment for code in rule.productCodes):
            return False

    # 🆕 5. 세부품명
    if rule.detailedItems:
        if not any(item.lower() in text for item in rule.detailedItems):
            return False

    # 6. 금액 범위
    if rule.minAmt and bid.get('estimatedAmt', 0) < rule.minAmt:
        return False
    if rule.maxAmt and bid.get('estimatedAmt', 0) > rule.maxAmt:
        return False

    return True  # 모든 조건 통과
```

**자체 리뷰:**
- ✅ 제외 필터 우선 처리 → 불필요한 LLM 호출 방지
- ✅ 대소문자 무시 (`.lower()`)
- ⚠️ 물품분류번호가 별도 필드로 존재하지 않으면 attachmentText 파싱 필요
- ⚠️ 정규식 활용 고려 (예: "교통신호등" vs "교통 신호등")

---

### Stage 2: LLM 자격요건 파싱 (Pro 버전, 향후)

**목적:** RFP 자격요건 텍스트를 LLM이 읽고 회사 프로필과 비교

```python
def apply_llm_filters(bid: dict[str, Any], profile: CompanyProfile) -> bool:
    """LLM 기반 2차 필터링 (Pro 버전)"""

    # RFP 자격요건 추출
    rfp_text = bid.get('attachmentText', '')
    if not rfp_text:
        return True  # RFP 없으면 통과 (메타데이터 필터만 적용)

    # LLM 프롬프트
    prompt = f"""
    다음 입찰 공고의 자격요건과 회사 프로필을 비교하여, 이 회사가 참여 가능한지 판단하세요.

    ## 공고 자격요건
    {rfp_text[:2000]}

    ## 회사 프로필
    {profile.description}

    ## 판단 기준
    - 소재지 제약: 공고에 "XX 소재 업체만" 같은 조건이 있으면 회사 프로필과 비교
    - 물품분류번호: 공고 요구사항과 회사 취급 품목 일치 여부
    - 필수 인증: 회사가 보유하지 않은 필수 인증이 있으면 불가

    응답: {{"eligible": true/false, "reason": "..."}}
    """

    response = call_llm_structured(prompt, schema={"eligible": "boolean", "reason": "string"})
    return response["eligible"]
```

**자체 리뷰:**
- ✅ Pro 버전 전용 기능 → 비용 통제
- ✅ RFP 텍스트 길이 제한 (2000자) → 토큰 비용 절감
- ⚠️ LLM 응답 신뢰도 검증 필요 (오판 시 중요 공고 놓칠 수 있음)
- ⚠️ `call_llm_structured()` 구현 필요 (기존 `call_with_retry` 활용)

---

## 마이그레이션 전략

### 기존 alert_test_*.json 파일 마이그레이션

현재 관리자 페이지에서 관리하는 `data/alert_states/alert_test_*.json` 파일을 새 형식으로 변환:

```python
def migrate_legacy_alerts():
    """레거시 알림 설정을 새 형식으로 마이그레이션"""
    legacy_dir = Path("data/alert_states")
    if not legacy_dir.exists():
        return

    for file_path in legacy_dir.glob("alert_test_*.json"):
        with open(file_path, 'r') as f:
            legacy = json.load(f)

        # 새 형식으로 변환
        new_config = {
            "email": legacy.get("email", "admin@example.com"),
            "enabled": legacy.get("enabled", True),
            "schedule": legacy.get("schedule", "daily_2"),
            "hours": legacy.get("hours", [9, 18]),
            "rules": [
                {
                    "id": rule["id"],
                    "keywords": rule["keywords"],
                    "excludeKeywords": rule.get("excludeKeywords", []),
                    "categories": rule.get("categories", []),
                    "regions": rule.get("regions", []),
                    "excludeRegions": [],  # 신규 필드 비워둠
                    "productCodes": [],
                    "detailedItems": [],
                    "minAmt": rule.get("minAmt"),
                    "maxAmt": rule.get("maxAmt"),
                    "enabled": rule.get("enabled", True),
                }
                for rule in legacy.get("rules", [])
            ],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        # 새 경로에 저장
        save_alert_config(new_config)
        print(f"Migrated: {file_path.name} → {new_config['email']}")
```

**실행 시점:** 첫 배포 시 1회 실행

**자체 리뷰:**
- ✅ 기존 설정 손실 방지
- ✅ 신규 필드는 빈 배열로 초기화
- ⚠️ 중복 이메일 처리 (여러 alert_test_*.json이 같은 이메일이면 덮어쓰기)

---

## 테스트 전략

### 1. 필터 로직 단위 테스트

```python
# tests/test_alert_matcher.py

def test_metadata_filter_keyword_match():
    """키워드 매칭 테스트"""
    bid = {"title": "교통신호등 설치 공사", "category": "물품"}
    rule = {"keywords": ["교통신호등"], "excludeKeywords": []}
    assert apply_metadata_filters(bid, rule) is True

def test_metadata_filter_exclude_keyword():
    """제외 키워드 테스트"""
    bid = {"title": "교통신호등 유지보수"}
    rule = {"keywords": ["교통신호등"], "excludeKeywords": ["유지보수"]}
    assert apply_metadata_filters(bid, rule) is False

def test_metadata_filter_exclude_region():
    """제외 지역 테스트"""
    bid = {"title": "신호등 설치", "region": "안산"}
    rule = {"keywords": ["신호등"], "excludeRegions": ["안산", "부산"]}
    assert apply_metadata_filters(bid, rule) is False

def test_product_code_matching():
    """물품분류번호 매칭 테스트"""
    bid = {"title": "CCTV 구매", "attachmentText": "물품분류번호: 42101"}
    rule = {"keywords": ["CCTV"], "productCodes": ["42101"]}
    assert apply_metadata_filters(bid, rule) is True
```

### 2. API 엔드포인트 테스트

```python
# tests/test_alert_api.py

def test_save_and_load_config(client):
    """설정 저장/조회 테스트"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "rules": [{"id": "1", "keywords": ["교통신호등"], "enabled": True}]
    }

    # 저장
    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 200

    # 조회
    resp = client.get("/api/alerts/config?email=test@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert len(data["rules"]) == 1

def test_preview_filters(client):
    """필터 미리보기 테스트"""
    payload = {
        "rules": [{"keywords": ["교통신호등"], "excludeRegions": ["안산"]}],
        "limit": 50
    }

    resp = client.post("/api/alerts/preview", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "matchCount" in data
    assert "samples" in data
```

### 3. UI 통합 테스트

```typescript
// frontend/kirabot/__tests__/AlertsPage.test.tsx

describe('AlertsPage', () => {
  it('renders alert settings form', () => {
    render(<AlertsPage />);
    expect(screen.getByText('알림 설정')).toBeInTheDocument();
    expect(screen.getByLabelText('이메일')).toBeInTheDocument();
  });

  it('saves alert config on submit', async () => {
    const mockSave = jest.fn();
    render(<AlertsPage onSave={mockSave} />);

    fireEvent.change(screen.getByLabelText('이메일'), {
      target: { value: 'user@example.com' }
    });
    fireEvent.click(screen.getByText('저장'));

    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledWith(expect.objectContaining({
        email: 'user@example.com'
      }));
    });
  });
});
```

---

## 보안 고려사항

### 1. 이메일 주소 노출 방지

- 파일명은 SHA256 해시 사용 → 이메일 역추적 불가
- API 응답에서도 이메일 마스킹 고려 (u***@example.com)

### 2. 입력 검증

- 이메일 형식 검증 (정규식 또는 email-validator)
- 키워드/지역 입력 길이 제한 (최대 100자)
- rules 배열 크기 제한 (최대 10개)

### 3. Rate Limiting

- `/api/alerts/preview` 엔드포인트: 1분당 5회 제한 (나라장터 API 보호)

---

## 배포 계획

### Phase 1: 메타데이터 필터 (Free)

- UI: AlertsPage + 기본 필터 섹션
- Backend: GET/POST /api/alerts/config, 메타데이터 필터 로직
- 기능: keywords, excludeKeywords, regions, excludeRegions, productCodes, detailedItems, amount range

### Phase 2: LLM 자격요건 파싱 (Pro)

- Backend: `apply_llm_filters()` 구현
- UI: CompanyProfile 섹션 활성화
- 요금제 체크 로직 추가

### Phase 3: 고도화

- 알림 히스토리 (받은 공고 목록)
- 통계 대시보드 (주간/월간 매칭 건수)
- 필터 성능 개선 (캐싱, 인덱싱)

---

## 예상 공수

| 항목 | 예상 시간 | 담당 |
|------|----------|------|
| 데이터 모델 확장 | 1h | Backend |
| Backend API 구현 (3개 엔드포인트) | 4h | Backend |
| 필터 매칭 로직 (메타데이터) | 3h | Backend |
| UI 컴포넌트 (AlertsPage 등 4개) | 6h | Frontend |
| Sidebar 메뉴 추가 | 1h | Frontend |
| 단위/통합 테스트 | 4h | QA |
| 마이그레이션 스크립트 | 1h | Backend |
| 문서화 | 1h | Tech Writer |
| **합계** | **21h** | |

---

## 자체 코드 리뷰 요약

### ✅ 강점

1. **점진적 확장**: 기존 AlertRule 구조 유지하며 필드 추가 → 하위 호환성
2. **2단계 필터**: 메타데이터(무료) + LLM(Pro) 분리 → 비용 통제
3. **사용자 자율성**: 직접 설정 가능 → 관리자 부담 감소
4. **미리보기 기능**: 필터 효과 즉시 확인 → 오설정 방지

### ⚠️ 개선 필요

1. **Pydantic 검증**: 현재 dict 기반 → 타입 안전성 약함. Pydantic 모델로 전환 권장
2. **물품분류번호 파싱**: attachmentText에서 추출 시 정규식 정확도 검증 필요
3. **LLM 신뢰도**: Stage 2 LLM 필터 오판 시 중요 공고 놓칠 위험 → A/B 테스트 필요
4. **확장성**: 파일 기반 저장 → 사용자 증가 시 SQLite/PostgreSQL 마이그레이션 고려

### 🔧 후속 작업

- [ ] 나라장터 API에서 물품분류번호 필드 확인 (별도 제공되는지)
- [ ] LLM 자격요건 파싱 프롬프트 정교화 (예시 케이스 10개 수집)
- [ ] 알림 발송 로직과 통합 (현재는 설정만 저장, 실제 발송은 별도 구현)
- [ ] 관리자 페이지에서 사용자 알림 설정 조회 기능 추가

---

## 결론

본 설계는 사용자가 직접 세부 필터링된 입찰 공고 알림을 설정할 수 있는 독립 UI와 2단계 필터링 시스템을 제공합니다. 메타데이터 기반 1차 필터는 무료로 제공하고, LLM 기반 2차 필터는 Pro 버전 전용으로 하여 비용을 통제합니다. 파일 기반 저장으로 빠르게 구현 가능하며, 향후 DB 마이그레이션으로 확장할 수 있습니다.
