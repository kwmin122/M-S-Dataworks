# 발주예측 페이지 대규모 업그레이드 설계

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 발주예측 페이지를 "그래서 뭘 보라는 건데?" 수준에서 "SI업체 사업본부장이 매일 보고 싶은 페이지"로 전환

**Architecture:** 백엔드 API 확장(12개월 데이터, 금액 집계, 카테고리 분포, **발주계획 사전공개 연동**) + 프론트엔드 완전 리디자인(인사이트 카드, 차트 탭, D-day 뱃지, **발주예정 섹션**, Empty State CTA). Phase 2에서 회사 프로필 연동 슬롯 활성화.

**Tech Stack:** React 19, TypeScript, Recharts, Framer Motion, FastAPI, 나라장터 Open API

---

## 현재 문제

발주예측 페이지(`/forecast`, `ForecastPage.tsx`)가 아무 가치도 전달하지 못함.

**현재 구성:**
1. 기관 검색 → 3개월 월별 건수 막대차트
2. "참고용" 하드코딩 면책 문구 (AI 아님)
3. 최근 공고 10건 테이블 (공고명, 마감일, 분류만)

**핵심 결함:**
- `totalAmt`가 항상 0 — 금액 데이터 미집계 (백엔드 버그)
- `estimatedPrice`가 BidNotice에 존재하지만 forecast에서 미사용
- AI 인사이트가 고정 문자열 — 진짜 분석 아님
- 3개월은 패턴 파악에 불충분 — 계절성 감지 불가
- "그래서 우리 회사와 뭔 상관?" 질문에 답 없음

---

## 타겟 사용자 & 핵심 질문

**사용자:** SI업체 입찰담당자 / 사업본부장

이 페이지에서 답을 얻고 싶은 4가지:
1. "이 기관이 **언제** 발주하는가?" (시기 예측)
2. "**얼마짜리** 사업을 주로 하는가?" (규모 파악)
3. "**우리랑 맞는** 사업인가?" (분야 매칭)
4. "지금 **준비해야 할 것**이 있는가?" (액션 아이템)

---

## 경쟁사 분석 요약

| 플랫폼 | 핵심 가치 |
|---|---|
| 클라이원트 | 공고 전 단계(발주계획)에서 기회 포착 — "골든 타임" |
| 비드프로 | 사정율 예측으로 낙찰 확률 계산 |
| 인포21C | 발주처 심층분석 + 경쟁사 투찰성향 |
| GovWin | Fit Score (40~100점) — 공고-회사 적합도 즉시 파악 |
| BGOV | 5년 지출 트렌드 + 예산 배분 시각화 |
| Fed-Spend | 재입찰 예측 (180일 전 알림) |

**공통 성공 공식:** `가치 = 시간 우위 × 개인화 × 행동 가능성`

---

## Phase 구분

| Phase | 범위 | 의존성 |
|---|---|---|
| **Phase 1** | 백엔드 API 확장 + **발주계획 사전공개 연동** + 프론트엔드 UI/UX 리디자인 | 없음 (즉시 시작 가능) |
| **Phase 2** | 회사 프로필 시스템 + 발주예측 맞춤 모드 | Phase 1 완료 후 |

> **발주계획현황서비스 API 확인 완료**: `apis.data.go.kr/1230000/ao/OrderPlanSttusService` — 기존 `DATA_GO_KR_API_KEY` 동일 사용 가능. 물품/공사/용역/외자 4개 카테고리, `orderInsttNm`(기관명) 검색 지원, 응답에 사업명/금액/조달방식/계약방법/담당자/연락처 포함.

---

## Phase 1: 백엔드 API 확장 + 프론트엔드 리디자인

### Task 1: 백엔드 — `/api/forecast/{기관명}` API 확장

**파일:** `services/web_app/main.py` (lines 2190-2231)

**변경사항:**

#### 1-A. 기간 12개월로 확장

현재: `period="3m"` 고정
변경: 커스텀 날짜 범위로 12개월 조회

```python
# nara_api.py의 _split_monthly_ranges가 30일 단위로 자동 분할하므로
# 직접 날짜 범위를 지정하여 12개월 데이터를 가져온다.
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
start_12m = now - timedelta(days=365)
```

nara_api.py에 `period` 대신 직접 `bgn_dt`/`end_dt`를 전달하는 방식 또는 `period="12m"` 옵션 추가.

#### 1-B. 금액 집계 (`totalAmt` 버그 수정)

현재: `monthly[month_key] = {"count": 0, "totalAmt": 0}` 후 count만 증가
변경: `estimatedPrice` 문자열에서 숫자를 파싱하여 합산

```python
# estimatedPrice 형식: "1,234,567원" 또는 None
raw_price = bid.get("estimatedPrice") or ""
amt = 0
if raw_price:
    try:
        amt = int(re.sub(r"[^0-9]", "", raw_price))
    except ValueError:
        pass
monthly[month_key]["totalAmt"] += amt
```

#### 1-C. 카테고리 분포 집계 추가

응답에 `categoryBreakdown` 필드 추가:

```python
# 카테고리별 건수 집계
category_counts: dict[str, int] = {}
for bid in notices:
    cat = bid.get("category", "기타")
    category_counts[cat] = category_counts.get(cat, 0) + 1
```

응답 구조:
```json
{
  "categoryBreakdown": {
    "용역": 45,
    "물품": 23,
    "공사": 12,
    "외자": 2,
    "기타": 5
  }
}
```

#### 1-D. page_size 확대

현재: `page_size=100` → 변경: `page_size=500`
12개월 데이터는 100건으로 부족. nara_api의 CHUNK_ROWS=500을 활용.

#### 1-E. 최종 API 응답 구조

```typescript
interface ForecastOrgData {
  orgName: string;
  monthlyPattern: Record<string, {
    count: number;
    totalAmt: number;    // 원 단위 정수 (0이면 데이터 없음)
  }>;
  categoryBreakdown: Record<string, number>;  // 신규
  recentBids: BidNotice[];  // 최대 20건 (현재 10건 → 확대)
  aiInsight: string;
  total: number;
}
```

---

### Task 2: 프론트엔드 — 페이지 헤더 개선

**파일:** `frontend/kirabot/components/forecast/ForecastPage.tsx`

현재: `<h1>발주예측</h1>` 만 있음
변경:

```tsx
<div className="mb-6">
  <h1 className="text-2xl font-bold text-slate-900">발주예측</h1>
  <p className="mt-1 text-sm text-slate-500">
    관심 기관의 과거 발주 패턴을 분석하여 향후 입찰 기회를 미리 파악하세요.
  </p>
</div>
```

---

### Task 3: 프론트엔드 — 인사이트 카드 4개

차트 위에 핵심 지표를 한눈에 보여주는 요약 카드 배치.

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ 📅 집중 발주 시기  │  │ 📈 발주 추세      │  │ 💰 평균 공고 규모  │  │ 📋 주요 분야      │
│   2월, 12월       │  │  전월 대비 +40%   │  │   약 2.3억원       │  │  용역 75%         │
│   (연간 패턴)     │  │  (최근 3개월↑)    │  │   (추정가격 기준)  │  │  물품 25%         │
└──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

**계산 로직 (프론트엔드에서 자동):**

```typescript
// 1. 집중 발주 시기: 건수가 가장 많은 상위 2개 월
const topMonths = Object.entries(monthlyPattern)
  .sort(([,a], [,b]) => b.count - a.count)
  .slice(0, 2)
  .map(([m]) => `${parseInt(m.slice(5))}월`);

// 2. 발주 추세: 최근 3개월 vs 이전 3개월 건수 비교
const sorted = Object.entries(monthlyPattern).sort(([a],[b]) => a.localeCompare(b));
const recent3 = sorted.slice(-3).reduce((s,[,v]) => s + v.count, 0);
const prev3 = sorted.slice(-6, -3).reduce((s,[,v]) => s + v.count, 0);
const trendPct = prev3 > 0 ? Math.round(((recent3 - prev3) / prev3) * 100) : null;

// 3. 평균 공고 규모: totalAmt > 0인 월만 평균
const amtEntries = Object.values(monthlyPattern).filter(v => v.totalAmt > 0);
const avgAmt = amtEntries.length > 0
  ? amtEntries.reduce((s, v) => s + v.totalAmt, 0) / total
  : null;

// 4. 주요 분야: categoryBreakdown에서 비율 계산
```

**카드 스타일:**

```
bg-white rounded-xl shadow-sm border border-slate-100 p-5
아이콘: bg-{color}-50 p-2 rounded-lg 내 lucide 아이콘
제목: text-xs font-medium text-slate-500 uppercase tracking-wider
수치: text-xl font-bold text-slate-900
부가정보: text-xs text-slate-400
```

데이터 부족 시: 해당 카드에 "데이터 수집 중" 회색 텍스트 표시 (카드 자체는 유지).

---

### Task 4: 프론트엔드 — 차트 개선

#### 4-A. 12개월 데이터 + 탭 (공고 건수 / 추정 금액)

```tsx
const [chartTab, setChartTab] = useState<'count' | 'amount'>('count');
```

차트 위에 2개 탭 버튼:
- `[공고 건수]` — 월별 count 막대차트 (현재와 유사)
- `[추정 금액]` — 월별 totalAmt 합산 막대차트

#### 4-B. Y축 정수 표시

현재: 0.5 단위 눈금이 나옴 (공고 1건일 때)
수정: `<YAxis allowDecimals={false} />`

#### 4-C. X축 라벨 개선

현재: "02" (월만 표시)
변경: "3월", "4월" 형식 — 12개월이면 연도 경계에서 "1월(26)" 같이 표시

```typescript
.map(([month, val]) => ({
  month,
  label: `${parseInt(month.slice(5))}월`,
  count: val.count,
  amount: val.totalAmt,
}))
```

#### 4-D. 금액 차트 포맷

Y축: `tickFormatter={(v) => v >= 1_0000_0000 ? `${(v/1_0000_0000).toFixed(1)}억` : `${(v/10000).toFixed(0)}만`}`
Tooltip: 금액을 "12억 3,400만원" 형식으로 표시

#### 4-E. Recharts 경고 수정

현재: `width(-1) and height(-1)` 경고
원인: framer-motion 애니메이션 중 컨테이너 크기가 0
수정: `chartReady` 상태를 유지하되, ResponsiveContainer에 `minWidth={100} minHeight={200}` 추가

---

### Task 5: 프론트엔드 — 최근 공고 목록 강화

현재: 공고명, 마감일, 분류 3칼럼
변경:

| 공고명 | 추정가격 | 마감일 | 분류 |
|---|---|---|---|
| SI 시스템 유지보수 | 2.3억 | D-3 (빨강) | 용역 |
| 네트워크 장비 구매 | 5,400만 | D-12 (노랑) | 물품 |
| 건물 보수공사 | - | 마감 (회색) | 공사 |

#### 5-A. 추정가격 컬럼

```typescript
function formatPrice(price?: string): string {
  if (!price) return '-';
  const num = parseInt(price.replace(/[^0-9]/g, ''));
  if (isNaN(num) || num === 0) return '-';
  if (num >= 1_0000_0000) return `${(num / 1_0000_0000).toFixed(1)}억`;
  if (num >= 10000) return `${Math.round(num / 10000).toLocaleString()}만`;
  return `${num.toLocaleString()}원`;
}
```

#### 5-B. D-day 뱃지

```typescript
function getDdayBadge(deadlineAt?: string): { text: string; color: string } {
  if (!deadlineAt) return { text: '-', color: 'slate' };
  const diff = Math.ceil((new Date(deadlineAt).getTime() - Date.now()) / 86400000);
  if (diff < 0) return { text: '마감', color: 'slate' };
  if (diff <= 7) return { text: `D-${diff}`, color: 'red' };
  if (diff <= 14) return { text: `D-${diff}`, color: 'amber' };
  return { text: `D-${diff}`, color: 'emerald' };
}
```

뱃지 스타일: `px-2 py-0.5 rounded-full text-xs font-medium`
- 빨강: `bg-red-50 text-red-700`
- 노랑: `bg-amber-50 text-amber-700`
- 초록: `bg-emerald-50 text-emerald-700`
- 회색: `bg-slate-100 text-slate-500`

#### 5-C. 공고 건수 확대

현재: 10건 → 변경: 20건 (백엔드도 20건으로 확대)

---

### Task 6: 프론트엔드 — Empty State 개선

데이터 없을 때 알림 설정으로 유도:

```tsx
{!loading && !data && (
  <div className="text-center py-16">
    <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100">
      <TrendingUp size={24} className="text-slate-400" />
    </div>
    <h3 className="text-lg font-semibold text-slate-700 mb-2">
      기관을 검색해보세요
    </h3>
    <p className="text-sm text-slate-400 mb-6 max-w-sm mx-auto">
      기관명을 검색하면 최근 12개월 발주 패턴, 금액 추이,
      주요 분야를 한눈에 확인할 수 있어요.
    </p>
  </div>
)}
```

데이터 조회 후 공고가 0건일 때:

```tsx
{!loading && data && data.total === 0 && (
  <div className="text-center py-16 rounded-xl border border-slate-200 bg-white">
    <Search size={32} className="text-slate-300 mx-auto mb-4" />
    <h3 className="text-lg font-medium text-slate-600 mb-2">
      최근 12개월 내 공고 데이터가 없습니다
    </h3>
    <p className="text-sm text-slate-400 mb-6">
      이 기관의 새로운 공고가 등록되면 알림을 받아보세요.
    </p>
    <button
      onClick={() => navigate('/settings/alerts')}
      className="px-4 py-2 bg-kira-600 text-white rounded-lg text-sm hover:bg-kira-700"
    >
      이 기관 알림 설정하기
    </button>
  </div>
)}
```

---

### Task 7: 프론트엔드 — 기관 검색 개선

#### 7-A. 최근 검색 히스토리 (localStorage)

```typescript
const RECENT_KEY = 'forecast_recent_orgs';
const MAX_RECENT = 5;

function getRecentOrgs(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); }
  catch { return []; }
}

function addRecentOrg(org: string) {
  const list = getRecentOrgs().filter(o => o !== org);
  list.unshift(org);
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, MAX_RECENT)));
}
```

검색 실행 시 `addRecentOrg(orgName)` 호출.
검색바 아래, 인기 기관 위에 최근 검색 칩 표시 (별도 스타일: `border-dashed`).

#### 7-B. 자동완성 (간단 버전)

인기 기관 목록 + 최근 검색에서 입력값과 매칭하여 드롭다운 표시.
(외부 API 없이 로컬 필터링만.)

---

### Task 8: nara_api.py — 12개월 기간 지원

**파일:** `services/web_app/nara_api.py`

`_build_date_range`과 `_split_monthly_ranges`에 `"12m"` 옵션 추가:

```python
delta_map = {
    "1w": timedelta(weeks=1),
    "1m": timedelta(days=30),
    "3m": timedelta(days=90),
    "6m": timedelta(days=180),
    "12m": timedelta(days=365),  # 추가
}
```

`_split_monthly_ranges`는 이미 30일 단위로 자동 분할하므로 12개월 = 12~13개 청크로 분할됨.
주의: API 호출 횟수가 많아지므로 `page_size`를 크게 잡고 병렬 요청 활용.

---

### Task 9: 백엔드 — 발주계획현황 API 클라이언트

**파일:** `services/web_app/nara_api.py` (기존 파일에 추가)

나라장터 **발주계획현황서비스** (`OrderPlanSttusService`) 연동.
기존 입찰공고 API와 동일한 패턴으로 구현.

#### API 정보

```
Base URL: https://apis.data.go.kr/1230000/ao/OrderPlanSttusService
인증: DATA_GO_KR_API_KEY (기존과 동일)
```

#### 카테고리 엔드포인트 (PPSSrch = 나라장터 검색조건 기반)

```python
ORDER_PLAN_API_BASE = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService"

ORDER_PLAN_ENDPOINTS: dict[str, str] = {
    "goods": "getOrderPlanSttusListThngPPSSrch",
    "service": "getOrderPlanSttusListServcPPSSrch",
    "construction": "getOrderPlanSttusListCnstwkPPSSrch",
    "foreign": "getOrderPlanSttusListFrgcptPPSSrch",
}
```

#### 검색 파라미터

```python
params = {
    "serviceKey": api_key,
    "numOfRows": "500",
    "pageNo": "1",
    "type": "json",
    "orderInsttNm": org_name,       # 발주기관명 (필수)
    "orderBgnYm": "202601",         # 발주시작년월 (필수)
    "orderEndYm": "202612",         # 발주종료년월 (필수)
    "inqryBgnDt": "202601010000",   # 조회시작일시 (필수)
    "inqryEndDt": "202612312359",   # 조회종료일시 (필수)
}
```

#### 응답 정규화 함수

```python
def _normalize_order_plan(item: dict[str, Any], category: str = "") -> dict[str, Any]:
    """발주계획 API 응답 item → OrderPlan dict."""
    return {
        "id": str(item.get("orderPlanUntyNo", "")).strip(),        # 발주계획통합번호
        "bizNm": str(item.get("bizNm", "")).strip(),               # 사업명
        "orderInsttNm": str(item.get("orderInsttNm", "")).strip(), # 발주기관명
        "orderYear": str(item.get("orderYear", "")).strip(),       # 발주년도
        "orderQuarter": str(item.get("orderQtr", "")).strip(),     # 발주분기
        "orderAmt": _parse_amt(item.get("orderContrctAmt")),       # 발주도급금액 (원)
        "sumOrderAmt": _parse_amt(item.get("sumOrderAmt")),        # 합계발주금액 (원)
        "prcrmntMethd": str(item.get("prcrmntMethd", "")).strip(), # 조달방식
        "cntrctMthdNm": str(item.get("cntrctMthdNm", "")).strip(), # 계약방법명
        "deptNm": str(item.get("deptNm", "")).strip(),             # 부서명
        "ofclNm": str(item.get("ofclNm", "")).strip(),             # 담당자명
        "telNo": str(item.get("telNo", "")).strip(),               # 전화번호
        "category": CATEGORY_LABEL.get(category, category),
        "bidNtceNoList": str(item.get("bidNtceNoList", "")).strip(), # 연결된 입찰공고번호
        "ntcePblancYn": str(item.get("ntcePblancYn", "")).strip(),  # 공고게시여부
    }

def _parse_amt(value: Any) -> int:
    """금액 문자열 → 정수 (원)."""
    if not value:
        return 0
    try:
        return int(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return 0
```

#### 검색 함수

```python
async def search_order_plans(
    *,
    org_name: str = "",
    year: int | None = None,
    category: str = "all",
) -> dict[str, Any]:
    """발주계획 검색.

    Returns:
        {"plans": [...], "total": int}
    """
    api_key = _get_api_key()
    now = _kst_now()
    yr = year or now.year

    # 해당 연도 전체 조회
    bgn_ym = f"{yr}01"
    end_ym = f"{yr}12"
    bgn_dt = f"{yr}01010000"
    end_dt = f"{yr}12312359"

    shared_params = {
        "serviceKey": api_key,
        "numOfRows": "500",
        "pageNo": "1",
        "type": "json",
        "orderBgnYm": bgn_ym,
        "orderEndYm": end_ym,
        "inqryBgnDt": bgn_dt,
        "inqryEndDt": end_dt,
    }
    if org_name:
        shared_params["orderInsttNm"] = org_name

    all_plans: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient() as client:
        endpoints = (
            [(category, ORDER_PLAN_ENDPOINTS[category])]
            if category != "all" and category in ORDER_PLAN_ENDPOINTS
            else list(ORDER_PLAN_ENDPOINTS.items())
        )
        for cat, endpoint in endpoints:
            url = f"{ORDER_PLAN_API_BASE}/{endpoint}"
            try:
                resp = await client.get(url, params=shared_params, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("발주계획 API 호출 실패 (%s): %s", endpoint, exc)
                continue

            items = _parse_items(data)
            for item in items:
                plan = _normalize_order_plan(item, cat)
                pid = plan["id"]
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_plans.append(plan)

    return {"plans": all_plans, "total": len(all_plans)}
```

---

### Task 10: 백엔드 — forecast API에 발주계획 데이터 통합

**파일:** `services/web_app/main.py`

`/api/forecast/{org_name}` 응답에 `orderPlans` 필드 추가:

```python
@app.get("/api/forecast/{org_name}")
async def get_org_forecast(org_name: str) -> dict[str, Any]:
    # ... 기존 12개월 공고 데이터 조회 (Task 1) ...

    # 발주계획 데이터 조회 (올해)
    order_plan_result = await nara_search_order_plans(org_name=org_name)
    order_plans = order_plan_result.get("plans", [])

    # 공고와 아직 미연결된 발주계획만 필터 (진짜 "예정" 사업)
    upcoming_plans = [
        p for p in order_plans
        if not p.get("bidNtceNoList")  # 입찰공고번호가 없으면 아직 공고 안 됨
        or p.get("ntcePblancYn") != "Y"  # 공고 미게시
    ]

    return {
        "orgName": org_name,
        "monthlyPattern": monthly,
        "categoryBreakdown": category_counts,
        "recentBids": notices[:20],
        "orderPlans": upcoming_plans,  # 신규: 발주예정 사업 목록
        "aiInsight": ai_insight,
        "total": total,
    }
```

#### 프론트엔드 타입 확장

```typescript
export interface OrderPlan {
  id: string;
  bizNm: string;           // 사업명
  orderInsttNm: string;    // 발주기관명
  orderYear: string;       // 발주년도
  orderQuarter: string;    // 발주분기 (1,2,3,4)
  orderAmt: number;        // 발주도급금액 (원)
  sumOrderAmt: number;     // 합계발주금액 (원)
  prcrmntMethd: string;    // 조달방식
  cntrctMthdNm: string;    // 계약방법명 (경쟁, 수의 등)
  deptNm: string;          // 부서명
  ofclNm: string;          // 담당자명
  telNo: string;           // 전화번호
  category: string;        // 물품/용역/공사/외자
  bidNtceNoList: string;   // 연결된 입찰공고번호 (빈 문자열이면 미공고)
  ntcePblancYn: string;    // 공고게시여부 (Y/N)
}

export interface ForecastOrgData {
  orgName: string;
  monthlyPattern: Record<string, { count: number; totalAmt: number }>;
  categoryBreakdown: Record<string, number>;
  recentBids: BidNotice[];
  orderPlans: OrderPlan[];  // 신규
  aiInsight: string;
  total: number;
}
```

---

### Task 11: 프론트엔드 — 발주예정(사전공개) 섹션

**파일:** `frontend/kirabot/components/forecast/ForecastPage.tsx`

인사이트 카드와 차트 사이에 **"발주예정 사업"** 섹션 추가.
공고가 아직 안 나온 사업만 표시 — 이것이 진짜 "예측" 가치.

```tsx
{data.orderPlans && data.orderPlans.length > 0 && (
  <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
    <div className="flex items-center gap-2 mb-4">
      <CalendarClock size={18} className="text-amber-600" />
      <h2 className="text-base font-semibold text-slate-900">
        발주예정 사업 ({data.orderPlans.length}건)
      </h2>
      <span className="text-xs text-amber-600 bg-amber-100 px-2 py-0.5 rounded-full font-medium">
        사전공개
      </span>
    </div>
    <p className="text-xs text-amber-700 mb-4">
      아직 입찰공고가 게시되지 않은 발주계획입니다. 미리 준비하세요.
    </p>
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-amber-200">
            <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">사업명</th>
            <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">예산</th>
            <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">예정 시기</th>
            <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">계약방법</th>
            <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">담당자</th>
          </tr>
        </thead>
        <tbody>
          {data.orderPlans.map(plan => (
            <tr key={plan.id} className="border-b border-amber-100 hover:bg-amber-100/50">
              <td className="py-2.5 px-2 max-w-xs">
                <div className="font-medium text-slate-900 truncate">{plan.bizNm}</div>
                <div className="text-xs text-slate-400">{plan.category}</div>
              </td>
              <td className="py-2.5 px-2 text-slate-700 whitespace-nowrap">
                {formatPrice(plan.orderAmt || plan.sumOrderAmt)}
              </td>
              <td className="py-2.5 px-2 text-slate-500 whitespace-nowrap">
                {plan.orderYear}년 {plan.orderQuarter}분기
              </td>
              <td className="py-2.5 px-2 text-slate-500">
                {plan.cntrctMthdNm || plan.prcrmntMethd || '-'}
              </td>
              <td className="py-2.5 px-2 text-slate-500">
                {plan.ofclNm && (
                  <div>
                    <span className="text-slate-700">{plan.ofclNm}</span>
                    {plan.telNo && (
                      <div className="text-xs text-slate-400">{plan.telNo}</div>
                    )}
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
)}
```

**핵심 가치**: "아직 공고도 안 나왔는데 이미 알고 준비할 수 있다" = **골든 타임**

---

## Phase 2: 회사 프로필 시스템 (향후)

### 핵심 컨셉

```
현재:  로그인 → 채팅 → (나중에) "회사 문서 올려주세요" → 세션에만 저장
Phase 2: 로그인 → "회사 정보 등록" → 영구 저장 → 모든 기능에서 자동 활용
```

### 설계 방향

1. **회사 프로필 페이지** (`/settings/company`)
   - 회사 문서 업로드 (사업자등록증, 실적증명서, 기술인력 현황 등)
   - 업로드된 문서에서 자동 정보 추출 (rfx_analyzer 활용)
   - 수동 보정: 회사명, 주요 분야, 보유 인증, 소재지 등

2. **영구 저장소**
   - 현재: `data/web_uploads/{session}/company/` (세션별, 휘발성)
   - 변경: `data/company_profiles/{user_id}/` (사용자별, 영구)
   - 추출된 프로필 JSON + 원본 파일 보관

3. **전체 기능 연동**
   - **발주예측**: 기관 공고 중 회사 적합도 점수 표시
   - **공고 검색**: 회사 역량 매칭 필터 / 적합도 순 정렬
   - **공고 분석**: 회사 문서 재업로드 없이 자동 매칭
   - **대시보드**: "이번 주 우리 회사에 맞는 새 공고 N건"

### Phase 2는 Phase 1에서 이렇게 준비

- `ForecastOrgData` 타입에 `fitScores?: Record<string, number>` 슬롯 예약
- 공고 목록에 "적합도" 컬럼 자리 확보 (데이터 없으면 숨김)
- 인사이트 카드에 "우리 회사 매칭률" 카드 슬롯 예약

---

---

## 구현 순서 (Phase 1)

| 순서 | Task | 설명 | 의존성 |
|---|---|---|---|
| 1 | Task 8 | nara_api.py에 `12m` 기간 추가 | 없음 |
| 2 | Task 9 | nara_api.py에 발주계획현황 API 클라이언트 추가 | 없음 |
| 3 | Task 1 | 백엔드 forecast API 확장 (12개월, 금액, 카테고리) | Task 8 |
| 4 | Task 10 | 백엔드 forecast API에 발주계획 데이터 통합 | Task 9 |
| 5 | Task 2 | 페이지 헤더 서브타이틀 | 없음 |
| 6 | Task 3 | 인사이트 카드 4개 | Task 1 (API 응답 구조) |
| 7 | Task 11 | 프론트엔드 발주예정 섹션 | Task 10 |
| 8 | Task 4 | 차트 개선 (탭, 12개월, Y축) | Task 1 |
| 9 | Task 5 | 공고 목록 강화 (금액, D-day) | Task 1 |
| 10 | Task 6 | Empty State 개선 | 없음 |
| 11 | Task 7 | 기관 검색 개선 | 없음 |

---

## 검증 기준

1. `npm run build` 성공
2. `/forecast` 페이지에서 기관 검색 시:
   - 인사이트 카드 4개 표시 (데이터에 따라 일부 "데이터 수집 중")
   - **발주예정 사업 섹션** 표시 (미공고 발주계획이 있을 때)
   - 12개월 막대차트 (건수 탭 기본)
   - 금액 탭 전환 시 금액 차트 표시
   - Y축이 정수만 표시
   - 공고 목록에 추정가격, D-day 뱃지 표시
3. Recharts `width(-1)` 콘솔 경고 없음
4. 데이터 0건 기관 → Empty State + 알림 설정 CTA 표시
5. 최근 검색 기관이 localStorage에 저장/표시
6. **발주계획 API 호출 성공** (동일 DATA_GO_KR_API_KEY 사용)
7. 발주예정 테이블에 사업명, 예산, 예정 시기, 계약방법, 담당자 표시

---

## 참고: API 출처

- [조달청_나라장터 입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do) — 기존 사용 중
- [조달청_나라장터 발주계획현황서비스](https://www.data.go.kr/data/15129462/openapi.do) — Phase 1에서 신규 연동
