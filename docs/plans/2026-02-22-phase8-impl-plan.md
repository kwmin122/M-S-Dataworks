# Phase 8 Implementation Plan — Kira Bot 올라운더

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 기존 RFx 분석 워크스페이스에 스마트 공고 검색·다중 평가·제안서 생성·HWP 처리 기능을 추가하여 경쟁사 대비 올라운더 포지셔닝 확립.

**Architecture:** 기존 Split-Pane Dashboard에 WorkspaceMode 탭 추가. Next.js API Routes로 검색/평가/엑셀/제안서 엔드포인트 신규 추가. PostgreSQL FTS(tsvector+GIN)로 첨부파일 본문 검색. rag_engine에 제안서 생성·HWP 파싱 엔드포인트 추가.

**Tech Stack:** Next.js 15 (App Router), Prisma 5.22, PostgreSQL 16 (tsvector+GIN), React 19 + Vite + TypeScript, exceljs, docxtemplater, python-hwp5, n8n

**설계 문서:** `docs/plans/2026-02-22-phase8-design.md`

**제약:** `frontend/kirabot/` CSS·레이아웃 전면 변경 금지. 기존 Tailwind 클래스 재사용.

---

## Wave 1 — 스마트 검색 + 다중 분석 (우선순위 최고)

### Task 18: Prisma — SavedSearch + BidInterest 모델 추가

**Files:**
- Modify: `web_saas/prisma/schema.prisma`

**Step 1: 스키마에 두 모델 추가**

`web_saas/prisma/schema.prisma` 파일 끝에 추가:

```prisma
model SavedSearch {
  id             String   @id @default(cuid())
  organizationId String   @map("organization_id")
  name           String
  conditions     Json
  createdAt      DateTime @default(now()) @map("created_at")
  updatedAt      DateTime @updatedAt @map("updated_at")
  @@map("saved_searches")
}

model BidInterest {
  id             String   @id @default(cuid())
  organizationId String   @map("organization_id")
  bidNoticeId    String   @map("bid_notice_id")
  status         String   @default("STARRED")
  createdAt      DateTime @default(now()) @map("created_at")
  @@unique([organizationId, bidNoticeId])
  @@map("bid_interests")
}
```

**Step 2: 마이그레이션 실행**

```bash
cd web_saas
npx prisma migrate dev --name add_saved_search_bid_interest
npx prisma generate
```

Expected: "Your database is now in sync with your schema."

**Step 3: 마이그레이션 파일 커밋**

```bash
git add web_saas/prisma/
git commit -m "feat(db): add SavedSearch and BidInterest models"
```

---

### Task 19: Next.js API — POST /api/search/bids (기본 필터 검색)

**Files:**
- Create: `web_saas/src/app/api/search/bids/route.ts`
- Create: `web_saas/src/lib/search/buildSearchQuery.ts`
- Create: `web_saas/src/lib/search/buildSearchQuery.test.ts`

**Step 1: 테스트 작성 (RED)**

`web_saas/src/lib/search/buildSearchQuery.test.ts`:

```typescript
import { buildSearchConditions } from './buildSearchQuery';

describe('buildSearchConditions', () => {
  it('빈 조건이면 빈 where 반환', () => {
    const result = buildSearchConditions({});
    expect(result).toEqual({});
  });

  it('keywords 배열로 title OR 조건 생성', () => {
    const result = buildSearchConditions({ keywords: ['CCTV', '통신'] });
    expect(result.OR).toHaveLength(2);
    expect(result.OR![0]).toEqual({ title: { contains: 'CCTV', mode: 'insensitive' } });
  });

  it('region 필터 포함', () => {
    const result = buildSearchConditions({ region: '경기' });
    expect(result.region).toEqual({ contains: '경기', mode: 'insensitive' });
  });

  it('금액 범위 필터', () => {
    const result = buildSearchConditions({ minAmt: 50000000, maxAmt: 300000000 });
    expect(result.estimatedAmt).toEqual({ gte: BigInt(50000000), lte: BigInt(300000000) });
  });

  it('excludeExpired=true이면 deadlineAt > now() 조건', () => {
    const before = new Date();
    const result = buildSearchConditions({ excludeExpired: true });
    expect(result.deadlineAt?.gt).toBeInstanceOf(Date);
    expect(result.deadlineAt!.gt! >= before).toBe(true);
  });
});
```

**Step 2: 테스트 실패 확인**

```bash
cd web_saas && npx jest src/lib/search/buildSearchQuery.test.ts
```

Expected: FAIL — "Cannot find module './buildSearchQuery'"

**Step 3: buildSearchQuery 구현**

`web_saas/src/lib/search/buildSearchQuery.ts`:

```typescript
interface SearchConditions {
  keywords?: string[];
  region?: string;
  minAmt?: number;
  maxAmt?: number;
  excludeExpired?: boolean;
}

export function buildSearchConditions(cond: SearchConditions): Record<string, unknown> {
  const where: Record<string, unknown> = {};

  if (cond.keywords?.length) {
    where.OR = cond.keywords.map((kw) => ({
      title: { contains: kw, mode: 'insensitive' },
    }));
  }

  if (cond.region) {
    where.region = { contains: cond.region, mode: 'insensitive' };
  }

  if (cond.minAmt != null || cond.maxAmt != null) {
    where.estimatedAmt = {
      ...(cond.minAmt != null ? { gte: BigInt(cond.minAmt) } : {}),
      ...(cond.maxAmt != null ? { lte: BigInt(cond.maxAmt) } : {}),
    };
  }

  if (cond.excludeExpired) {
    where.deadlineAt = { gt: new Date() };
  }

  return where;
}
```

**Step 4: 테스트 통과 확인**

```bash
cd web_saas && npx jest src/lib/search/buildSearchQuery.test.ts
```

Expected: PASS (5/5)

**Step 5: API Route 구현**

`web_saas/src/app/api/search/bids/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { buildSearchConditions } from '@/lib/search/buildSearchQuery';

export async function POST(req: NextRequest) {
  const body = await req.json() as {
    keywords?: string[];
    region?: string;
    minAmt?: number;
    maxAmt?: number;
    excludeExpired?: boolean;
    limit?: number;
  };

  const where = buildSearchConditions({
    keywords: body.keywords,
    region: body.region,
    minAmt: body.minAmt,
    maxAmt: body.maxAmt,
    excludeExpired: body.excludeExpired,
  });

  const notices = await prisma.bidNotice.findMany({
    where: where as Parameters<typeof prisma.bidNotice.findMany>[0]['where'],
    orderBy: { publishedAt: 'desc' },
    take: body.limit ?? 50,
    select: {
      id: true,
      title: true,
      region: true,
      category: true,
      url: true,
      publishedAt: true,
      deadlineAt: true,
      source: true,
      externalId: true,
    },
  });

  return NextResponse.json({ notices, total: notices.length });
}
```

**Step 6: 커밋**

```bash
git add web_saas/src/lib/search/ web_saas/src/app/api/search/
git commit -m "feat(api): add POST /api/search/bids with filter conditions"
```

---

### Task 20: Next.js API — 배치 평가 트리거 + 엑셀 출력

**Files:**
- Create: `web_saas/src/app/api/evaluate/batch/route.ts`
- Create: `web_saas/src/app/api/export/evaluations/route.ts`
- Create: `web_saas/src/lib/export/buildEvaluationExcel.ts`
- Create: `web_saas/src/lib/export/buildEvaluationExcel.test.ts`

**Step 1: exceljs 설치**

```bash
cd web_saas && npm install exceljs
```

**Step 2: 엑셀 빌더 테스트 작성 (RED)**

`web_saas/src/lib/export/buildEvaluationExcel.test.ts`:

```typescript
import { buildEvaluationExcel } from './buildEvaluationExcel';

const mockRows = [
  {
    title: '경기도 CCTV 교체',
    estimatedAmt: null,
    deadlineAt: new Date('2026-03-15'),
    region: '경기',
    isEligible: true,
    evaluationReason: 'GO 판정',
    actionPlan: '실적증명서 준비',
    url: 'https://g2b.go.kr/1',
  },
];

describe('buildEvaluationExcel', () => {
  it('Buffer를 반환한다', async () => {
    const buf = await buildEvaluationExcel(mockRows);
    expect(buf).toBeInstanceOf(Buffer);
    expect(buf.length).toBeGreaterThan(0);
  });

  it('빈 배열도 처리한다', async () => {
    const buf = await buildEvaluationExcel([]);
    expect(buf).toBeInstanceOf(Buffer);
  });
});
```

**Step 3: 테스트 실패 확인**

```bash
cd web_saas && npx jest src/lib/export/buildEvaluationExcel.test.ts
```

Expected: FAIL — "Cannot find module"

**Step 4: buildEvaluationExcel 구현**

`web_saas/src/lib/export/buildEvaluationExcel.ts`:

```typescript
import ExcelJS from 'exceljs';

interface EvalRow {
  title: string;
  estimatedAmt: bigint | null;
  deadlineAt: Date | null;
  region: string | null;
  isEligible: boolean | null;
  evaluationReason: string;
  actionPlan: string | null;
  url: string | null;
}

const HEADERS = [
  '공고명', '금액(원)', '마감일', '지역', 'GO/NO-GO', '판정근거', '준비액션', '공고URL',
];

export async function buildEvaluationExcel(rows: EvalRow[]): Promise<Buffer> {
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet('공고 분석 결과');

  ws.addRow(HEADERS);
  ws.getRow(1).font = { bold: true };

  for (const r of rows) {
    ws.addRow([
      r.title,
      r.estimatedAmt != null ? Number(r.estimatedAmt) : '',
      r.deadlineAt ? r.deadlineAt.toISOString().slice(0, 10) : '',
      r.region ?? '',
      r.isEligible === true ? 'GO' : r.isEligible === false ? 'NO-GO' : '미평가',
      r.evaluationReason,
      r.actionPlan ?? '',
      r.url ?? '',
    ]);
  }

  return wb.xlsx.writeBuffer() as Promise<Buffer>;
}
```

**Step 5: 테스트 통과 확인**

```bash
cd web_saas && npx jest src/lib/export/buildEvaluationExcel.test.ts
```

Expected: PASS (2/2)

**Step 6: 배치 평가 트리거 Route**

`web_saas/src/app/api/evaluate/batch/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

export async function POST(req: NextRequest) {
  const { bidNoticeIds, organizationId } = await req.json() as {
    bidNoticeIds: string[];
    organizationId: string;
  };

  if (!bidNoticeIds?.length || !organizationId) {
    return NextResponse.json({ error: 'bidNoticeIds and organizationId required' }, { status: 400 });
  }

  const org = await prisma.organization.findUnique({ where: { id: organizationId } });
  if (!org) return NextResponse.json({ error: 'Organization not found' }, { status: 404 });

  const jobs = await Promise.all(
    bidNoticeIds.map((bidNoticeId) =>
      prisma.evaluationJob.upsert({
        where: {
          idempotencyKey: `batch_${organizationId}_${bidNoticeId}`,
        },
        create: {
          id: createId(),
          organizationId,
          bidNoticeId,
          idempotencyKey: `batch_${organizationId}_${bidNoticeId}`,
          noticeRevision: 'batch',
          evaluationReason: 'user_requested',
        },
        update: {},
      })
    )
  );

  return NextResponse.json({ jobsCreated: jobs.length, jobs });
}
```

**Step 7: 엑셀 내보내기 Route**

`web_saas/src/app/api/export/evaluations/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { buildEvaluationExcel } from '@/lib/export/buildEvaluationExcel';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const organizationId = searchParams.get('organizationId');
  if (!organizationId) {
    return NextResponse.json({ error: 'organizationId required' }, { status: 400 });
  }

  const jobs = await prisma.evaluationJob.findMany({
    where: { organizationId },
    include: { bidNotice: true },
    orderBy: { createdAt: 'desc' },
    take: 200,
  });

  const rows = jobs.map((j) => ({
    title: j.bidNotice.title,
    estimatedAmt: null,
    deadlineAt: j.bidNotice.deadlineAt,
    region: j.bidNotice.region,
    isEligible: j.isEligible,
    evaluationReason: j.evaluationReason,
    actionPlan: j.actionPlan,
    url: j.bidNotice.url,
  }));

  const buffer = await buildEvaluationExcel(rows);

  return new NextResponse(buffer, {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'Content-Disposition': 'attachment; filename="kirabot_evaluations.xlsx"',
    },
  });
}
```

**Step 8: 커밋**

```bash
git add web_saas/src/lib/export/ web_saas/src/app/api/evaluate/ web_saas/src/app/api/export/
git commit -m "feat(api): add batch evaluation trigger + Excel export endpoint"
```

---

### Task 21: Frontend — Dashboard 워크스페이스 탭 추가

**Files:**
- Modify: `frontend/kirabot/components/Dashboard.tsx`
- Create: `frontend/kirabot/components/workspace/SearchPanel.tsx`
- Create: `frontend/kirabot/components/workspace/MultiAnalysisPanel.tsx`

**Step 1: Dashboard.tsx에 WorkspaceMode 타입 + 탭 추가**

`Dashboard.tsx`의 기존 타입 선언 블록에 추가:

```typescript
type WorkspaceMode = 'rfx' | 'search' | 'multi' | 'proposal';
```

Dashboard 컴포넌트 state에 추가:
```typescript
const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>('rfx');
```

우측 패널 상단 헤더 `<div className="flex h-14 ...">` 안에 탭 버튼 추가
(기존 "Kira 워크스페이스" h3 태그 바로 아래):

```tsx
const WORKSPACE_TABS: { mode: WorkspaceMode; label: string }[] = [
  { mode: 'rfx', label: 'RFx 분석' },
  { mode: 'search', label: '공고 검색' },
  { mode: 'multi', label: '다중 분석' },
  { mode: 'proposal', label: '제안서' },
];
```

헤더 아래 탭 바 삽입 (기존 파일 업로드 div 위):

```tsx
<div className="flex border-b border-slate-200 bg-white px-4">
  {WORKSPACE_TABS.map((tab) => (
    <button
      key={tab.mode}
      type="button"
      onClick={() => setWorkspaceMode(tab.mode)}
      className={`px-3 py-2 text-xs font-medium border-b-2 -mb-px ${
        workspaceMode === tab.mode
          ? 'border-primary-600 text-primary-700'
          : 'border-transparent text-slate-500 hover:text-slate-700'
      }`}
    >
      {tab.label}
    </button>
  ))}
</div>
```

기존 파일 업로드 + 채팅 영역을 `workspaceMode === 'rfx'`일 때만 렌더링:

```tsx
{workspaceMode === 'rfx' && (
  <>
    {/* 기존 파일 업로드 div */}
    {/* 기존 채팅 flex-1 div */}
    {/* 기존 입력 bottom div */}
  </>
)}
{workspaceMode === 'search' && <SearchPanel organizationId={user?.id ?? ''} />}
{workspaceMode === 'multi' && <MultiAnalysisPanel organizationId={user?.id ?? ''} />}
{workspaceMode === 'proposal' && <div className="flex-1 flex items-center justify-center text-sm text-slate-400">제안서 기능 준비 중 (Wave 3)</div>}
```

**Step 2: SearchPanel 기본 컴포넌트 생성**

`frontend/kirabot/components/workspace/SearchPanel.tsx`:

```tsx
import React, { useState } from 'react';
import { Search, MessageSquare, AlignLeft } from 'lucide-react';
import Button from '../Button';

type SearchMode = 'interview' | 'form';

interface SearchConditions {
  keywords: string[];
  region: string;
  minAmt: string;
  maxAmt: string;
  period: '1w' | '1m' | '3m';
  excludeExpired: boolean;
}

interface BidResult {
  id: string;
  title: string;
  region: string | null;
  deadlineAt: string | null;
  url: string | null;
}

interface SearchPanelProps {
  organizationId: string;
}

const PERIOD_LABELS = { '1w': '최근 1주', '1m': '최근 1개월', '3m': '최근 3개월' };

const SearchPanel: React.FC<SearchPanelProps> = ({ organizationId }) => {
  const [mode, setMode] = useState<SearchMode>('form');
  const [conditions, setConditions] = useState<SearchConditions>({
    keywords: [],
    region: '',
    minAmt: '',
    maxAmt: '',
    period: '1m',
    excludeExpired: true,
  });
  const [keywordInput, setKeywordInput] = useState('');
  const [results, setResults] = useState<BidResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const addKeyword = () => {
    const kw = keywordInput.trim();
    if (kw && !conditions.keywords.includes(kw)) {
      setConditions((prev) => ({ ...prev, keywords: [...prev.keywords, kw] }));
    }
    setKeywordInput('');
  };

  const removeKeyword = (kw: string) => {
    setConditions((prev) => ({ ...prev, keywords: prev.keywords.filter((k) => k !== kw) }));
  };

  const handleSearch = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/search/bids', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keywords: conditions.keywords,
          region: conditions.region || undefined,
          minAmt: conditions.minAmt ? Number(conditions.minAmt) : undefined,
          maxAmt: conditions.maxAmt ? Number(conditions.maxAmt) : undefined,
          excludeExpired: conditions.excludeExpired,
        }),
      });
      const data = await res.json() as { notices: BidResult[] };
      setResults(data.notices);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* 모드 선택 */}
      <div className="flex gap-2 p-3 border-b border-slate-200 bg-slate-50">
        <button
          type="button"
          onClick={() => setMode('form')}
          className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium border ${
            mode === 'form' ? 'border-primary-600 bg-primary-50 text-primary-700' : 'border-slate-300 bg-white text-slate-600'
          }`}
        >
          <AlignLeft className="h-3 w-3" /> 폼 입력
        </button>
        <button
          type="button"
          onClick={() => setMode('interview')}
          className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium border ${
            mode === 'interview' ? 'border-primary-600 bg-primary-50 text-primary-700' : 'border-slate-300 bg-white text-slate-600'
          }`}
        >
          <MessageSquare className="h-3 w-3" /> Kira와 대화
        </button>
      </div>

      {mode === 'form' && (
        <div className="flex flex-col gap-3 p-4 overflow-y-auto border-b border-slate-200">
          {/* 키워드 */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">키워드</label>
            <div className="flex gap-2">
              <input
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addKeyword()}
                placeholder="예: CCTV, 통신망"
                className="flex-1 h-8 rounded-lg border border-slate-300 px-2 text-xs outline-none focus:border-primary-500"
              />
              <button
                type="button"
                onClick={addKeyword}
                className="rounded-lg border border-slate-300 bg-white px-2 text-xs text-slate-600 hover:bg-slate-50"
              >
                추가
              </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {conditions.keywords.map((kw) => (
                <span
                  key={kw}
                  className="flex items-center gap-1 rounded-full bg-primary-50 px-2 py-0.5 text-[11px] text-primary-700"
                >
                  {kw}
                  <button type="button" onClick={() => removeKeyword(kw)} className="text-primary-400 hover:text-primary-700">×</button>
                </span>
              ))}
            </div>
          </div>

          {/* 지역 */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">지역</label>
            <input
              value={conditions.region}
              onChange={(e) => setConditions((prev) => ({ ...prev, region: e.target.value }))}
              placeholder="예: 경기, 서울"
              className="w-full h-8 rounded-lg border border-slate-300 px-2 text-xs outline-none focus:border-primary-500"
            />
          </div>

          {/* 금액 범위 */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">금액 범위 (원)</label>
            <div className="flex items-center gap-2">
              <input
                value={conditions.minAmt}
                onChange={(e) => setConditions((prev) => ({ ...prev, minAmt: e.target.value }))}
                placeholder="최소"
                className="flex-1 h-8 rounded-lg border border-slate-300 px-2 text-xs outline-none focus:border-primary-500"
              />
              <span className="text-xs text-slate-400">~</span>
              <input
                value={conditions.maxAmt}
                onChange={(e) => setConditions((prev) => ({ ...prev, maxAmt: e.target.value }))}
                placeholder="최대"
                className="flex-1 h-8 rounded-lg border border-slate-300 px-2 text-xs outline-none focus:border-primary-500"
              />
            </div>
          </div>

          {/* 기간 */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">기간</label>
            <div className="flex gap-2">
              {(['1w', '1m', '3m'] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setConditions((prev) => ({ ...prev, period: p }))}
                  className={`rounded-lg border px-2 py-1 text-xs ${
                    conditions.period === p ? 'border-primary-600 bg-primary-50 text-primary-700' : 'border-slate-300 bg-white text-slate-600'
                  }`}
                >
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>
          </div>

          {/* 마감 제외 */}
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={conditions.excludeExpired}
              onChange={(e) => setConditions((prev) => ({ ...prev, excludeExpired: e.target.checked }))}
              className="rounded"
            />
            마감된 공고 제외
          </label>

          <Button size="sm" onClick={handleSearch} disabled={isLoading} className="w-full">
            {isLoading ? '검색 중...' : <><Search className="h-3 w-3 mr-1 inline" /> 검색하기</>}
          </Button>
        </div>
      )}

      {mode === 'interview' && (
        <div className="flex-1 flex items-center justify-center text-sm text-slate-400 p-4 text-center">
          인터뷰 모드: Kira가 대화로 검색 조건을 완성합니다.<br/>
          <span className="text-xs mt-1 block">(Wave 1 완성 후 연결 예정)</span>
        </div>
      )}

      {/* 검색 결과 */}
      {results.length > 0 && (
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <p className="text-xs font-semibold text-slate-600">{results.length}건 발견</p>
          {results.map((r) => (
            <div key={r.id} className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
              <p className="font-medium text-slate-800 leading-snug">{r.title}</p>
              <div className="mt-1 flex gap-3 text-slate-500">
                <span>{r.region || '-'}</span>
                <span>마감: {r.deadlineAt ? r.deadlineAt.slice(0, 10) : '-'}</span>
              </div>
              {r.url && (
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="mt-1 text-primary-600 hover:underline block">
                  공고 원문 보기
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchPanel;
```

**Step 3: MultiAnalysisPanel 기본 컴포넌트**

`frontend/kirabot/components/workspace/MultiAnalysisPanel.tsx`:

```tsx
import React, { useState } from 'react';
import { Download } from 'lucide-react';
import Button from '../Button';

interface EvalJob {
  id: string;
  bidNoticeId: string;
  isEligible: boolean | null;
  evaluationReason: string;
  actionPlan: string | null;
  bidNotice: {
    title: string;
    region: string | null;
    deadlineAt: string | null;
    url: string | null;
  };
}

interface MultiAnalysisPanelProps {
  organizationId: string;
}

const MultiAnalysisPanel: React.FC<MultiAnalysisPanelProps> = ({ organizationId }) => {
  const [jobs, setJobs] = useState<EvalJob[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadJobs = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/internal/evaluation-jobs?organizationId=${organizationId}`);
      const data = await res.json() as { jobs: EvalJob[] };
      setJobs(data.jobs);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExcel = () => {
    window.open(`/api/export/evaluations?organizationId=${organizationId}`, '_blank');
  };

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="flex items-center justify-between p-3 border-b border-slate-200 bg-slate-50">
        <Button size="sm" onClick={loadJobs} disabled={isLoading}>
          {isLoading ? '불러오는 중...' : '평가 결과 조회'}
        </Button>
        <button
          type="button"
          onClick={handleExcel}
          disabled={!jobs.length}
          className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          <Download className="h-3 w-3" /> 엑셀 다운로드
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {jobs.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            평가 결과가 없습니다. 공고 검색 후 평가를 실행하세요.
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">공고명</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">지역</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">마감</th>
                <th className="px-3 py-2 text-center font-semibold text-slate-600">판정</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {jobs.map((j) => (
                <tr key={j.id} className="hover:bg-slate-50">
                  <td className="px-3 py-2 text-slate-700 max-w-[160px] truncate">{j.bidNotice.title}</td>
                  <td className="px-3 py-2 text-slate-500">{j.bidNotice.region || '-'}</td>
                  <td className="px-3 py-2 text-slate-500">
                    {j.bidNotice.deadlineAt ? j.bidNotice.deadlineAt.slice(0, 10) : '-'}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {j.isEligible === true && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700 font-semibold">GO</span>}
                    {j.isEligible === false && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">NO-GO</span>}
                    {j.isEligible === null && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-700">대기</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default MultiAnalysisPanel;
```

**Step 4: 빌드 확인**

```bash
cd frontend/kirabot && npm run build
```

Expected: 빌드 성공, 타입 에러 없음

**Step 5: 커밋**

```bash
git add frontend/kirabot/components/
git commit -m "feat(ui): add workspace tabs + SearchPanel + MultiAnalysisPanel"
```

---

### Task 22: Next.js API — 평가 결과 조회 엔드포인트 (MultiAnalysisPanel 연결)

**Files:**
- Create: `web_saas/src/app/api/internal/evaluation-jobs/route.ts`

**Step 1: Route 구현**

`web_saas/src/app/api/internal/evaluation-jobs/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const organizationId = searchParams.get('organizationId');

  if (!organizationId) {
    return NextResponse.json({ error: 'organizationId required' }, { status: 400 });
  }

  const jobs = await prisma.evaluationJob.findMany({
    where: { organizationId },
    include: {
      bidNotice: {
        select: { title: true, region: true, deadlineAt: true, url: true },
      },
    },
    orderBy: { createdAt: 'desc' },
    take: 100,
  });

  return NextResponse.json({ jobs });
}
```

**Step 2: 커밋**

```bash
git add web_saas/src/app/api/internal/evaluation-jobs/
git commit -m "feat(api): add GET /api/internal/evaluation-jobs for MultiAnalysisPanel"
```

---

## Wave 2 — 첨부파일 전문 검색 + 강점 카드

### Task 23: PostgreSQL FTS — BidNotice.attachment_text에 GIN 인덱스 추가

**Files:**
- Create: `web_saas/prisma/migrations/<timestamp>_fts_attachment_gin/migration.sql` (자동 생성)

**Step 1: Prisma raw SQL 마이그레이션 생성**

```bash
cd web_saas
npx prisma migrate dev --name fts_attachment_gin --create-only
```

**Step 2: 생성된 migration.sql 파일에 GIN 인덱스 추가**

생성된 `migration.sql` 파일에 아래 내용을 추가:

```sql
-- 첨부파일 본문 FTS 인덱스 (한국어/영어 simple 사전 사용)
ALTER TABLE bid_notices
  ADD COLUMN IF NOT EXISTS attachment_tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(attachment_text, ''))
  ) STORED;

CREATE INDEX IF NOT EXISTS bid_notices_attachment_tsv_gin
  ON bid_notices USING GIN (attachment_tsv);
```

**Step 3: 마이그레이션 적용**

```bash
cd web_saas && npx prisma migrate dev
```

Expected: 마이그레이션 적용 완료

**Step 4: 커밋**

```bash
git add web_saas/prisma/
git commit -m "feat(db): add GIN FTS index on bid_notices attachment_text"
```

---

### Task 24: FTS 검색 API 통합 — /api/search/bids에 본문 검색 추가

**Files:**
- Modify: `web_saas/src/lib/search/buildSearchQuery.ts`
- Create: `web_saas/src/lib/search/ftsSearch.ts`
- Create: `web_saas/src/lib/search/ftsSearch.test.ts`

**Step 1: FTS 헬퍼 테스트 작성 (RED)**

`web_saas/src/lib/search/ftsSearch.test.ts`:

```typescript
import { buildFtsQuery } from './ftsSearch';

describe('buildFtsQuery', () => {
  it('단일 키워드 tsquery 생성', () => {
    expect(buildFtsQuery(['CCTV'])).toBe('CCTV');
  });

  it('다중 키워드 OR 연결', () => {
    expect(buildFtsQuery(['CCTV', '통신'])).toBe('CCTV | 통신');
  });

  it('빈 배열이면 빈 문자열', () => {
    expect(buildFtsQuery([])).toBe('');
  });

  it('특수문자 제거', () => {
    expect(buildFtsQuery(["CCTV's"])).toBe('CCTVs');
  });
});
```

**Step 2: 테스트 실패 확인**

```bash
cd web_saas && npx jest src/lib/search/ftsSearch.test.ts
```

Expected: FAIL

**Step 3: ftsSearch 구현**

`web_saas/src/lib/search/ftsSearch.ts`:

```typescript
export function buildFtsQuery(keywords: string[]): string {
  if (!keywords.length) return '';
  const sanitized = keywords.map((kw) => kw.replace(/['"\\]/g, '').trim()).filter(Boolean);
  return sanitized.join(' | ');
}
```

**Step 4: 테스트 통과 확인**

```bash
cd web_saas && npx jest src/lib/search/ftsSearch.test.ts
```

Expected: PASS (4/4)

**Step 5: /api/search/bids Route에 FTS 옵션 추가**

`web_saas/src/app/api/search/bids/route.ts`의 POST 핸들러에 FTS 분기 추가:

```typescript
import { buildFtsQuery } from '@/lib/search/ftsSearch';

// POST 핸들러 내부에 추가:
const { includeAttachmentText } = body as { includeAttachmentText?: boolean };

let notices;
if (includeAttachmentText && body.keywords?.length) {
  const ftsQuery = buildFtsQuery(body.keywords);
  notices = await prisma.$queryRaw<Array<{
    id: string; title: string; region: string | null;
    published_at: Date | null; deadline_at: Date | null; url: string | null;
  }>>`
    SELECT id, title, region, published_at, deadline_at, url
    FROM bid_notices
    WHERE attachment_tsv @@ plainto_tsquery('simple', ${ftsQuery})
    ORDER BY published_at DESC NULLS LAST
    LIMIT 50
  `;
  // camelCase 변환
  notices = notices.map((n) => ({
    id: n.id, title: n.title, region: n.region,
    publishedAt: n.published_at, deadlineAt: n.deadline_at, url: n.url,
  }));
} else {
  notices = await prisma.bidNotice.findMany({
    where: where as Parameters<typeof prisma.bidNotice.findMany>[0]['where'],
    orderBy: { publishedAt: 'desc' },
    take: body.limit ?? 50,
    select: { id: true, title: true, region: true, category: true, url: true, publishedAt: true, deadlineAt: true, source: true, externalId: true },
  });
}
```

**Step 6: SearchPanel에 첨부파일 검색 토글 추가**

`SearchPanel.tsx` 폼 내부에 토글 추가:

```tsx
<label className="flex items-center gap-2 text-xs text-slate-600">
  <input
    type="checkbox"
    checked={conditions.includeAttachmentText ?? false}
    onChange={(e) => setConditions((prev) => ({ ...prev, includeAttachmentText: e.target.checked }))}
    className="rounded"
  />
  첨부파일 본문 포함 검색 (조달AI 수준)
</label>
```

**Step 7: 커밋**

```bash
git add web_saas/src/lib/search/ web_saas/src/app/api/search/ frontend/kirabot/components/workspace/
git commit -m "feat: add attachment FTS search (GIN index + plainto_tsquery)"
```

---

### Task 25: Next.js API — GET /api/strength-card/:bidNoticeId

**Files:**
- Create: `web_saas/src/app/api/strength-card/[bidNoticeId]/route.ts`
- Create: `web_saas/src/lib/strengthCard/buildStrengthCard.ts`
- Create: `web_saas/src/lib/strengthCard/buildStrengthCard.test.ts`

**Step 1: 강점 카드 로직 테스트 작성 (RED)**

`web_saas/src/lib/strengthCard/buildStrengthCard.test.ts`:

```typescript
import { matchStrengths } from './buildStrengthCard';

describe('matchStrengths', () => {
  const companyFacts = {
    licenses: ['정보통신공사업', '전기공사업'],
    region: '경기',
    certifications: ['CC인증'],
    revenue: 500000000,
  };

  it('면허 보유 시 strengths에 포함', () => {
    const { strengths, gaps } = matchStrengths(companyFacts, {
      requiredLicenses: ['정보통신공사업'],
      region: '경기',
      minRevenue: 300000000,
    });
    expect(strengths.some((s) => s.includes('정보통신'))).toBe(true);
    expect(gaps).toHaveLength(0);
  });

  it('면허 미보유 시 gaps에 포함', () => {
    const { gaps } = matchStrengths(companyFacts, {
      requiredLicenses: ['건설업면허'],
      region: '경기',
    });
    expect(gaps.some((g) => g.includes('건설업'))).toBe(true);
  });
});
```

**Step 2: 테스트 실패 확인**

```bash
cd web_saas && npx jest src/lib/strengthCard/
```

Expected: FAIL

**Step 3: buildStrengthCard 구현**

`web_saas/src/lib/strengthCard/buildStrengthCard.ts`:

```typescript
interface CompanyFacts {
  licenses?: string[];
  region?: string;
  certifications?: string[];
  revenue?: number;
}

interface BidRequirements {
  requiredLicenses?: string[];
  region?: string;
  minRevenue?: number;
}

export function matchStrengths(
  company: CompanyFacts,
  requirements: BidRequirements
): { strengths: string[]; gaps: string[] } {
  const strengths: string[] = [];
  const gaps: string[] = [];

  for (const lic of requirements.requiredLicenses ?? []) {
    if (company.licenses?.some((l) => l.includes(lic) || lic.includes(l))) {
      strengths.push(`${lic} 면허 보유`);
    } else {
      gaps.push(`${lic} 면허 미보유 (공고 요건: 필수)`);
    }
  }

  if (requirements.region && company.region === requirements.region) {
    strengths.push(`${requirements.region} 지역 활동 이력`);
  }

  if (requirements.minRevenue && company.revenue) {
    if (company.revenue >= requirements.minRevenue) {
      strengths.push(`매출 기준 충족 (${(company.revenue / 100000000).toFixed(1)}억원)`);
    } else {
      gaps.push(`매출 기준 미충족 (요건: ${(requirements.minRevenue / 100000000).toFixed(1)}억원 이상)`);
    }
  }

  return { strengths, gaps };
}
```

**Step 4: 테스트 통과 확인**

```bash
cd web_saas && npx jest src/lib/strengthCard/
```

Expected: PASS (2/2)

**Step 5: API Route 구현**

`web_saas/src/app/api/strength-card/[bidNoticeId]/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { matchStrengths } from '@/lib/strengthCard/buildStrengthCard';

export async function GET(
  req: NextRequest,
  { params }: { params: { bidNoticeId: string } }
) {
  const { searchParams } = new URL(req.url);
  const organizationId = searchParams.get('organizationId');

  if (!organizationId) {
    return NextResponse.json({ error: 'organizationId required' }, { status: 400 });
  }

  const [notice, org] = await Promise.all([
    prisma.bidNotice.findUnique({ where: { id: params.bidNoticeId } }),
    prisma.organization.findUnique({ where: { id: organizationId } }),
  ]);

  if (!notice || !org) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const facts = org.companyFacts as Record<string, unknown>;
  // 공고 분석 결과에서 요건 추출 (EvaluationJob.details 활용)
  const evalJob = await prisma.evaluationJob.findFirst({
    where: { organizationId, bidNoticeId: params.bidNoticeId },
    orderBy: { createdAt: 'desc' },
  });

  const requirements = (evalJob?.details as Record<string, unknown>) ?? {};
  const { strengths, gaps } = matchStrengths(
    facts as Parameters<typeof matchStrengths>[0],
    requirements as Parameters<typeof matchStrengths>[1]
  );

  return NextResponse.json({
    notice: { title: notice.title, region: notice.region, deadlineAt: notice.deadlineAt },
    strengths,
    gaps,
    isEligible: evalJob?.isEligible ?? null,
    actionPlan: evalJob?.actionPlan ?? null,
  });
}
```

**Step 6: 커밋**

```bash
git add web_saas/src/lib/strengthCard/ web_saas/src/app/api/strength-card/
git commit -m "feat(api): add strength card endpoint + matchStrengths logic"
```

---

## Wave 3 — 제안서 초안 생성 + HWP 처리

### Task 26: Prisma — ProposalDraft 모델 추가

**Files:**
- Modify: `web_saas/prisma/schema.prisma`

**Step 1: ProposalDraft 모델 추가**

```prisma
model ProposalDraft {
  id             String   @id @default(cuid())
  organizationId String   @map("organization_id")
  bidNoticeId    String   @map("bid_notice_id")
  templateKey    String?  @map("template_key")
  draftKey       String?  @map("draft_key")
  status         String   @default("PENDING")
  createdAt      DateTime @default(now()) @map("created_at")
  updatedAt      DateTime @updatedAt @map("updated_at")
  @@map("proposal_drafts")
}
```

**Step 2: 마이그레이션**

```bash
cd web_saas && npx prisma migrate dev --name add_proposal_draft
git add web_saas/prisma/ && git commit -m "feat(db): add ProposalDraft model"
```

---

### Task 27: rag_engine — /api/generate-proposal 엔드포인트

**Files:**
- Create: `rag_engine/proposal_generator.py`
- Create: `rag_engine/tests/test_proposal_generator.py`
- Modify: `rag_engine/main.py`

**Step 1: 의존성 설치**

```bash
cd rag_engine && pip install docxtemplater python-docx
```

**Step 2: 테스트 작성 (RED)**

`rag_engine/tests/test_proposal_generator.py`:

```python
import pytest
from proposal_generator import extract_template_sections, fill_template_sections

def test_extract_sections_empty():
    """빈 텍스트 → 빈 섹션 dict"""
    result = extract_template_sections("")
    assert isinstance(result, dict)

def test_fill_sections_returns_string():
    sections = {"사업개요": "{{사업개요}}", "수행전략": "{{수행전략}}"}
    notice_text = "경기도청 CCTV 교체사업 입찰공고"
    result = fill_template_sections(sections, notice_text, company_info={"name": "테스트"})
    assert isinstance(result, dict)
    assert "사업개요" in result
```

**Step 3: 테스트 실패 확인**

```bash
cd rag_engine && python -m pytest tests/test_proposal_generator.py -v
```

Expected: FAIL — ImportError

**Step 4: proposal_generator 구현**

`rag_engine/proposal_generator.py`:

```python
from __future__ import annotations
import re
from typing import Any


def extract_template_sections(template_text: str) -> dict[str, str]:
    """DOCX 텍스트에서 {{섹션명}} 플레이스홀더를 파싱한다."""
    pattern = r'\{\{([^}]+)\}\}'
    placeholders = re.findall(pattern, template_text)
    return {p: f'{{{{{p}}}}}' for p in dict.fromkeys(placeholders)}


def fill_template_sections(
    sections: dict[str, str],
    notice_text: str,
    company_info: dict[str, Any],
) -> dict[str, str]:
    """각 섹션에 대해 AI 없이 기본 초안 텍스트를 생성한다 (LLM 연동은 호출 측에서 처리)."""
    filled: dict[str, str] = {}
    company_name = company_info.get("name", "당사")
    for section_name in sections:
        if '개요' in section_name or '배경' in section_name:
            filled[section_name] = f"본 사업은 {notice_text[:100]}에 관한 사업입니다. {company_name}은 이 분야에서 풍부한 경험을 보유하고 있습니다."
        elif '전략' in section_name:
            filled[section_name] = f"{company_name}의 핵심 수행 전략은 품질 우선, 일정 준수, 고객 소통입니다."
        elif '실적' in section_name:
            filled[section_name] = f"{company_name}의 최근 유사 수행 실적을 첨부합니다."
        else:
            filled[section_name] = f"[{section_name}에 대한 내용을 작성해주세요]"
    return filled
```

**Step 5: 테스트 통과 확인**

```bash
cd rag_engine && python -m pytest tests/test_proposal_generator.py -v
```

Expected: PASS (2/2)

**Step 6: main.py에 엔드포인트 추가**

`rag_engine/main.py`에 추가:

```python
from proposal_generator import extract_template_sections, fill_template_sections

class GenerateProposalRequest(BaseModel):
    notice_text: str
    template_text: str = ""
    company_info: dict = {}

class GenerateProposalResponse(BaseModel):
    sections: dict[str, str]
    status: str

@app.post("/api/generate-proposal", response_model=GenerateProposalResponse)
async def generate_proposal(req: GenerateProposalRequest):
    sections = extract_template_sections(req.template_text) if req.template_text else {
        "사업 개요": "{{사업 개요}}",
        "수행 전략": "{{수행 전략}}",
        "유사 실적": "{{유사 실적}}",
    }
    filled = fill_template_sections(sections, req.notice_text, req.company_info)
    return GenerateProposalResponse(sections=filled, status="done")
```

**Step 7: 커밋**

```bash
git add rag_engine/
git commit -m "feat(rag_engine): add /api/generate-proposal endpoint + proposal_generator"
```

---

### Task 28: Next.js API — POST /api/proposals + Frontend 제안서 탭 기본 UI

**Files:**
- Create: `web_saas/src/app/api/proposals/route.ts`
- Modify: `frontend/kirabot/components/Dashboard.tsx` (제안서 탭 placholder → 실제 컴포넌트)
- Create: `frontend/kirabot/components/workspace/ProposalPanel.tsx`

**Step 1: Proposals API Route**

`web_saas/src/app/api/proposals/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

export async function POST(req: NextRequest) {
  const { organizationId, bidNoticeId } = await req.json() as {
    organizationId: string;
    bidNoticeId: string;
  };

  if (!organizationId || !bidNoticeId) {
    return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
  }

  const notice = await prisma.bidNotice.findUnique({ where: { id: bidNoticeId } });
  if (!notice) return NextResponse.json({ error: 'BidNotice not found' }, { status: 404 });

  const org = await prisma.organization.findUnique({ where: { id: organizationId } });
  if (!org) return NextResponse.json({ error: 'Organization not found' }, { status: 404 });

  // rag_engine 호출
  const ragUrl = process.env.FASTAPI_URL ?? 'http://localhost:8001';
  const ragRes = await fetch(`${ragUrl}/api/generate-proposal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      notice_text: `${notice.title} ${notice.attachmentText ?? ''}`.slice(0, 2000),
      company_info: org.companyFacts,
    }),
  });

  const ragData = await ragRes.json() as { sections: Record<string, string>; status: string };

  const draft = await prisma.proposalDraft.create({
    data: {
      id: createId(),
      organizationId,
      bidNoticeId,
      status: 'DONE',
    },
  });

  return NextResponse.json({ draft, sections: ragData.sections });
}
```

**Step 2: ProposalPanel 컴포넌트**

`frontend/kirabot/components/workspace/ProposalPanel.tsx`:

```tsx
import React, { useState } from 'react';
import { FileDown } from 'lucide-react';
import Button from '../Button';

interface ProposalSection {
  [key: string]: string;
}

interface ProposalPanelProps {
  organizationId: string;
}

const ProposalPanel: React.FC<ProposalPanelProps> = ({ organizationId }) => {
  const [bidNoticeId, setBidNoticeId] = useState('');
  const [sections, setSections] = useState<ProposalSection | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [editedSections, setEditedSections] = useState<ProposalSection>({});

  const handleGenerate = async () => {
    if (!bidNoticeId.trim()) return;
    setIsLoading(true);
    try {
      const res = await fetch('/api/proposals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ organizationId, bidNoticeId }),
      });
      const data = await res.json() as { sections: ProposalSection };
      setSections(data.sections);
      setEditedSections(data.sections);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = () => {
    if (!editedSections) return;
    const text = Object.entries(editedSections)
      .map(([k, v]) => `## ${k}\n\n${v}`)
      .join('\n\n---\n\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'proposal_draft.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="flex items-center gap-2 p-3 border-b border-slate-200 bg-slate-50">
        <input
          value={bidNoticeId}
          onChange={(e) => setBidNoticeId(e.target.value)}
          placeholder="공고 ID 입력"
          className="flex-1 h-8 rounded-lg border border-slate-300 px-2 text-xs outline-none focus:border-primary-500"
        />
        <Button size="sm" onClick={handleGenerate} disabled={isLoading || !bidNoticeId}>
          {isLoading ? '생성 중...' : '초안 생성'}
        </Button>
        {sections && (
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
          >
            <FileDown className="h-3 w-3" /> 다운로드
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {!sections ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400 text-center">
            공고 ID를 입력하고 초안 생성을 누르세요.<br/>
            <span className="text-xs mt-1 block">회사 프로필 정보가 자동으로 반영됩니다.</span>
          </div>
        ) : (
          Object.entries(editedSections).map(([key, value]) => (
            <div key={key} className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs font-semibold text-slate-700 mb-1">{key}</p>
              <textarea
                value={value}
                onChange={(e) => setEditedSections((prev) => ({ ...prev, [key]: e.target.value }))}
                className="w-full text-xs text-slate-600 leading-relaxed outline-none resize-none min-h-[60px]"
                rows={3}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ProposalPanel;
```

**Step 3: Dashboard.tsx 제안서 탭 연결**

`Dashboard.tsx`에서 placeholder를 실제 컴포넌트로 교체:

```tsx
import ProposalPanel from './workspace/ProposalPanel';

// 기존 placeholder:
// {workspaceMode === 'proposal' && <div>...준비 중...</div>}
// 교체:
{workspaceMode === 'proposal' && <ProposalPanel organizationId={user?.id ?? ''} />}
```

**Step 4: 빌드 확인**

```bash
cd frontend/kirabot && npm run build
```

Expected: 빌드 성공

**Step 5: 커밋**

```bash
git add web_saas/src/app/api/proposals/ frontend/kirabot/components/workspace/ProposalPanel.tsx frontend/kirabot/components/Dashboard.tsx
git commit -m "feat: add proposal draft generation (rag_engine + UI + API)"
```

---

## Wave 4 — 발주계획 사전감지 (R&D)

### Task 29: Prisma — PreBidSignal 모델 + n8n 사전감지 워크플로우

**Files:**
- Modify: `web_saas/prisma/schema.prisma`
- Create: `n8n/workflows/pre_bid_crawler.json`
- Create: `web_saas/src/app/api/pre-bid-signals/route.ts`

**Step 1: PreBidSignal 모델 추가**

```prisma
model PreBidSignal {
  id           String    @id @default(cuid())
  source       String
  externalId   String    @map("external_id")
  title        String
  estimatedAmt BigInt?   @map("estimated_amt")
  region       String?
  estimatedAt  DateTime? @map("estimated_at")
  isEstimate   Boolean   @default(true) @map("is_estimate")
  createdAt    DateTime  @default(now()) @map("created_at")
  @@unique([source, externalId])
  @@map("pre_bid_signals")
}
```

```bash
cd web_saas && npx prisma migrate dev --name add_pre_bid_signal
```

**Step 2: 사전감지 API Route**

`web_saas/src/app/api/pre-bid-signals/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const region = searchParams.get('region');

  const signals = await prisma.preBidSignal.findMany({
    where: region ? { region: { contains: region, mode: 'insensitive' } } : {},
    orderBy: { createdAt: 'desc' },
    take: 50,
  });

  return NextResponse.json({ signals });
}
```

**Step 3: 커밋**

```bash
git add web_saas/prisma/ web_saas/src/app/api/pre-bid-signals/
git commit -m "feat(db+api): add PreBidSignal model and pre-bid signals endpoint"
```

---

## Wave 5 — HWP 처리 고도화

### Task 30: rag_engine — HWP 파싱 엔드포인트

**Files:**
- Create: `rag_engine/hwp_parser.py`
- Create: `rag_engine/tests/test_hwp_parser.py`
- Modify: `rag_engine/main.py`

**Step 1: python-hwp5 설치**

```bash
cd rag_engine && pip install hwp5
```

**Step 2: 테스트 작성 (RED)**

`rag_engine/tests/test_hwp_parser.py`:

```python
from hwp_parser import extract_hwp_text_bytes, is_hwp_bytes

def test_is_hwp_bytes_false_for_empty():
    assert is_hwp_bytes(b"") is False

def test_is_hwp_bytes_false_for_pdf():
    assert is_hwp_bytes(b"%PDF-1.4") is False

def test_extract_hwp_text_bytes_returns_str():
    """빈 바이트도 빈 문자열 반환 (실제 HWP 없이 기본 동작 검증)"""
    result = extract_hwp_text_bytes(b"notahwpfile")
    assert isinstance(result, str)
```

**Step 3: 테스트 실패 확인**

```bash
cd rag_engine && python -m pytest tests/test_hwp_parser.py -v
```

Expected: FAIL — ImportError

**Step 4: hwp_parser 구현**

`rag_engine/hwp_parser.py`:

```python
from __future__ import annotations
import io
import logging

logger = logging.getLogger(__name__)

# HWP compound document magic bytes
HWP_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'


def is_hwp_bytes(data: bytes) -> bool:
    """HWP 5.x compound document 파일인지 매직바이트로 확인."""
    return len(data) >= 8 and data[:8] == HWP_MAGIC


def extract_hwp_text_bytes(data: bytes) -> str:
    """HWP 바이트에서 텍스트를 추출한다. 파싱 실패 시 빈 문자열 반환."""
    if not is_hwp_bytes(data):
        logger.warning("Not a valid HWP file (magic bytes mismatch)")
        return ""

    try:
        import hwp5.hwp5txt as hwp5txt  # type: ignore
        import hwp5.filestructure as fs  # type: ignore

        hwp_file = fs.Hwp5File(io.BytesIO(data))
        out = io.StringIO()
        hwp5txt.generate_text(hwp_file, out)
        return out.getvalue()
    except Exception as exc:
        logger.error("HWP parsing failed: %s", exc)
        return ""
```

**Step 5: 테스트 통과 확인**

```bash
cd rag_engine && python -m pytest tests/test_hwp_parser.py -v
```

Expected: PASS (3/3)

**Step 6: main.py에 HWP 파싱 엔드포인트 추가**

```python
from hwp_parser import extract_hwp_text_bytes
from fastapi import UploadFile, File

@app.post("/api/parse-hwp")
async def parse_hwp(file: UploadFile = File(...)):
    data = await file.read()
    text = extract_hwp_text_bytes(data)
    if not text:
        return {"text": "", "success": False, "error": "파싱 실패 또는 HWP 형식 아님"}
    return {"text": text, "success": True, "char_count": len(text)}
```

**Step 7: 커밋**

```bash
git add rag_engine/
git commit -m "feat(rag_engine): add HWP text extraction + /api/parse-hwp endpoint"
```

---

## 전체 테스트 검증

**모든 Wave 완료 후 실행:**

```bash
# Jest 단위 테스트 (web_saas)
cd web_saas && npx jest --passWithNoTests
# Expected: ALL PASS

# FastAPI 테스트 (rag_engine)
cd rag_engine && python -m pytest tests/ -v
# Expected: ALL PASS

# TypeScript 빌드
cd frontend/kirabot && npm run build
# Expected: exit 0, no type errors

# TypeScript 타입 체크 (web_saas)
cd web_saas && npx tsc --noEmit
# Expected: exit 0
```

---

## 실행 방식 선택

**두 가지 실행 옵션:**

**1. Subagent-Driven (현재 세션)** — 태스크별 독립 서브에이전트 디스패치, 리뷰 후 다음 태스크
- `superpowers:subagent-driven-development` 스킬 사용

**2. Parallel Session (별도 세션)** — 새 세션에서 이 계획 파일 참조 후 실행
- `superpowers:executing-plans` 스킬 사용
