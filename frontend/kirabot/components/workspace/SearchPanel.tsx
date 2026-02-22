import React, { useState } from 'react';
import { AlignLeft, MessageSquare, Search } from 'lucide-react';
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

const SearchPanel: React.FC<SearchPanelProps> = ({ organizationId: _organizationId }) => {
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

          <Button size="sm" onClick={() => void handleSearch()} disabled={isLoading} className="w-full">
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
