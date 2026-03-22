import React, { useState } from 'react';
import { Search, Upload, Loader2, CheckCircle2, X, ExternalLink, AlertCircle, ChevronDown, ChevronUp, FileText, Zap } from 'lucide-react';
import Button from '../../Button';
import type { StudioProject } from '../../../services/studioApi';
import { searchNaraBids, type NaraBidNotice, type NaraSearchParams } from '../../../services/studioApi';

const MAX_UPLOAD_SIZE_MB = 20;
const ALLOWED_EXTENSIONS = new Set(['.pdf', '.docx', '.hwp', '.hwpx', '.txt', '.xlsx', '.pptx']);

const REGION_OPTIONS = [
  { code: '', label: '전국 (전체)' },
  { code: '11', label: '서울' },
  { code: '26', label: '부산' },
  { code: '27', label: '대구' },
  { code: '28', label: '인천' },
  { code: '29', label: '광주' },
  { code: '30', label: '대전' },
  { code: '31', label: '울산' },
  { code: '36', label: '세종' },
  { code: '41', label: '경기' },
  { code: '42', label: '강원' },
  { code: '43', label: '충북' },
  { code: '44', label: '충남' },
  { code: '45', label: '전북' },
  { code: '46', label: '전남' },
  { code: '47', label: '경북' },
  { code: '48', label: '경남' },
  { code: '50', label: '제주' },
];

interface RfpStageProps {
  project: StudioProject;
  onAnalyze: (text: string) => Promise<void>;
  onClassify: () => Promise<void>;
  onProjectUpdate?: () => void;
}

export default function RfpStage({ project, onAnalyze, onClassify, onProjectUpdate }: RfpStageProps) {
  const [rfpText, setRfpText] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [error, setError] = useState('');

  // 나라장터 검색 state
  const [showSearch, setShowSearch] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [searchCategory, setSearchCategory] = useState('all');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<NaraBidNotice[]>([]);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searchPage, setSearchPage] = useState(1);
  const [hasSearched, setHasSearched] = useState(false);

  // 고급 필터 state
  const [showFilters, setShowFilters] = useState(false);
  const [filterRegionCode, setFilterRegionCode] = useState('');
  const [filterMinAmt, setFilterMinAmt] = useState('');
  const [filterMaxAmt, setFilterMaxAmt] = useState('');
  const [filterPeriod, setFilterPeriod] = useState('1m');
  const [filterIndustry, setFilterIndustry] = useState('');
  const [filterBidCloseExcl, setFilterBidCloseExcl] = useState(true);

  const hasSnapshot = !!project.active_analysis_snapshot_id;

  const handleAnalyze = async () => {
    if (rfpText.trim().length < 50) {
      setError('공고 내용을 50자 이상 입력해주세요.');
      return;
    }
    setAnalyzing(true);
    setError('');
    try {
      await onAnalyze(rfpText);
      setRfpText('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'RFP 분석 실패';
      setError(msg);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleClassify = async () => {
    setClassifying(true);
    setError('');
    try {
      await onClassify();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '패키지 분류 실패';
      setError(msg);
    } finally {
      setClassifying(false);
    }
  };

  const handleSearch = async (page = 1) => {
    setSearching(true);
    setError('');
    try {
      const params: NaraSearchParams = {
        keywords: searchKeyword.trim(),
        category: searchCategory,
        page,
        bid_close_excl: filterBidCloseExcl,
        period: filterPeriod,
      };
      if (filterRegionCode) params.region_code = filterRegionCode;
      if (filterMinAmt) params.min_amt = parseFloat(filterMinAmt) * 10000; // 만원 → 원
      if (filterMaxAmt) params.max_amt = parseFloat(filterMaxAmt) * 10000;
      if (filterIndustry) params.industry = filterIndustry;

      const result = await searchNaraBids(params);
      setSearchResults(result.notices);
      setSearchTotal(result.total);
      setSearchPage(page);
      setHasSearched(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '검색 실패';
      setError(msg);
    } finally {
      setSearching(false);
    }
  };

  const handleSelectBid = (bid: NaraBidNotice) => {
    const lines = [
      `[공고명] ${bid.title}`,
      `[공고번호] ${bid.id}`,
      `[발주기관] ${bid.issuingOrg}`,
      bid.demandOrg ? `[수요기관] ${bid.demandOrg}` : '',
      bid.region ? `[지역] ${bid.region}` : '',
      bid.estimatedPrice ? `[추정가격] ${bid.estimatedPrice}` : '',
      bid.contractMethod ? `[계약방법] ${bid.contractMethod}` : '',
      bid.awardMethod ? `[낙찰방식] ${bid.awardMethod}` : '',
      bid.deadlineAt ? `[마감일] ${bid.deadlineAt}` : '',
      bid.category ? `[분류] ${bid.category}` : '',
      bid.detailUrl || bid.url ? `[공고URL] ${bid.detailUrl || bid.url}` : '',
    ].filter(Boolean).join('\n');
    setRfpText(lines);
    setShowSearch(false);
  };

  const handleSelectAndAnalyze = async (bid: NaraBidNotice) => {
    const lines = [
      `[공고명] ${bid.title}`,
      `[공고번호] ${bid.id}`,
      `[발주기관] ${bid.issuingOrg}`,
      bid.demandOrg ? `[수요기관] ${bid.demandOrg}` : '',
      bid.region ? `[지역] ${bid.region}` : '',
      bid.estimatedPrice ? `[추정가격] ${bid.estimatedPrice}` : '',
      bid.contractMethod ? `[계약방법] ${bid.contractMethod}` : '',
      bid.awardMethod ? `[낙찰방식] ${bid.awardMethod}` : '',
      bid.deadlineAt ? `[마감일] ${bid.deadlineAt}` : '',
      bid.category ? `[분류] ${bid.category}` : '',
      bid.detailUrl || bid.url ? `[공고URL] ${bid.detailUrl || bid.url}` : '',
    ].filter(Boolean).join('\n');
    setRfpText(lines);
    setShowSearch(false);
    setAnalyzing(true);
    setError('');
    try {
      await onAnalyze(lines);
      setRfpText('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'RFP 분석 실패';
      setError(msg);
    } finally {
      setAnalyzing(false);
    }
  };

  const formatDeadline = (deadline: string | null) => {
    if (!deadline) return '-';
    const d = new Date(deadline);
    const now = new Date();
    const diffMs = d.getTime() - now.getTime();
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    const dateStr = `${d.getMonth() + 1}/${d.getDate()}`;
    if (diffDays < 0) return `${dateStr} (마감)`;
    if (diffDays === 0) return `${dateStr} (오늘 마감)`;
    if (diffDays <= 3) return `${dateStr} (D-${diffDays})`;
    if (diffDays <= 7) return `${dateStr} (D-${diffDays})`;
    return dateStr;
  };

  const formatPrice = (price: string | null) => {
    if (!price) return '-';
    // "1,091,193,636원" → "10.9억" 같은 축약
    const raw = parseFloat(price.replace(/[^0-9.]/g, ''));
    if (!raw || isNaN(raw)) return price;
    if (raw >= 100_000_000) return `${(raw / 100_000_000).toFixed(1)}억`;
    if (raw >= 10_000) return `${(raw / 10_000).toFixed(0)}만`;
    return price;
  };

  const activeFilterCount =
    (filterRegionCode ? 1 : 0) +
    (filterMinAmt ? 1 : 0) +
    (filterMaxAmt ? 1 : 0) +
    (filterIndustry ? 1 : 0) +
    (filterPeriod !== '1m' ? 1 : 0) +
    (filterBidCloseExcl ? 0 : 1); // 마감 포함이 비기본값

  return (
    <div className="max-w-2xl">
      <h2 className="text-lg font-bold text-slate-900 mb-1">공고 분석</h2>
      <p className="text-sm text-slate-500 mb-6">
        입찰 공고를 입력하면 자동으로 분석하고 제출 패키지를 분류합니다.
      </p>

      {/* Snapshot status */}
      {hasSnapshot && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 mb-6">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 size={18} className="text-green-600" />
            <span className="text-sm font-semibold text-green-800">분석 완료</span>
          </div>
          <p className="text-xs text-green-700 ml-6">
            분석 스냅샷이 연결되어 있습니다. 제출 패키지 분류를 실행하거나, 새로운 공고를 다시 분석할 수 있습니다.
          </p>
        </div>
      )}

      {/* Text input */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-700 mb-2">
          공고 내용 입력
        </label>
        <textarea
          value={rfpText}
          onChange={(e) => setRfpText(e.target.value)}
          placeholder="공고문 전문 또는 주요 내용을 붙여넣기 해주세요. (최소 50자)"
          className="w-full h-48 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-kira-500 focus:border-transparent resize-y"
          disabled={analyzing}
        />
        <div className="flex justify-between mt-1.5">
          <span className="text-xs text-slate-400">
            {rfpText.length}자
          </span>
          <Button onClick={handleAnalyze} size="sm" disabled={analyzing || rfpText.trim().length < 50}>
            {analyzing ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span className="ml-1">분석 중...</span>
              </>
            ) : (
              '공고 분석'
            )}
          </Button>
        </div>
      </div>

      {/* Input method buttons */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <button
          onClick={() => setShowSearch(!showSearch)}
          className={`flex items-center gap-2 rounded-xl border p-3 transition-colors ${
            showSearch
              ? 'border-kira-500 bg-kira-50 text-kira-700'
              : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
          }`}
        >
          <Search size={16} />
          <span className="text-xs font-medium">나라장터 검색</span>
        </button>
        <label
          className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 text-slate-600 hover:border-slate-300 hover:bg-slate-50 cursor-pointer transition-colors"
        >
          <Upload size={16} />
          <span className="text-xs font-medium">파일 업로드</span>
          <input
            type="file"
            className="hidden"
            accept=".pdf,.docx,.hwp,.hwpx,.txt,.xlsx,.pptx"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) {
                e.target.value = '';
                return;
              }

              // Client-side validation: file size
              const sizeMB = file.size / (1024 * 1024);
              if (sizeMB > MAX_UPLOAD_SIZE_MB) {
                setError(`파일 크기가 너무 큽니다 (${sizeMB.toFixed(1)}MB). 최대 ${MAX_UPLOAD_SIZE_MB}MB까지 업로드 가능합니다.`);
                e.target.value = '';
                return;
              }

              // Client-side validation: file extension
              const ext = '.' + (file.name.split('.').pop()?.toLowerCase() ?? '');
              if (!ALLOWED_EXTENSIONS.has(ext)) {
                setError(`지원하지 않는 파일 형식입니다 (${ext}). PDF, DOCX, HWP, HWPX, TXT, XLSX, PPTX 파일만 가능합니다.`);
                e.target.value = '';
                return;
              }

              setAnalyzing(true);
              setError('');
              try {
                const { uploadAndAnalyzeRfp } = await import('../../../services/studioApi');
                await uploadAndAnalyzeRfp(project.id, file);
                // Refresh project state (upload already analyzed on backend)
                onProjectUpdate?.();
              } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : '파일 분석 실패';
                setError(msg);
              } finally {
                setAnalyzing(false);
                e.target.value = '';
              }
            }}
            disabled={analyzing}
          />
        </label>
      </div>

      {/* Nara Search Panel */}
      {showSearch && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-800">나라장터 공고 검색</h3>
            <button onClick={() => setShowSearch(false)} className="text-slate-400 hover:text-slate-600">
              <X size={16} />
            </button>
          </div>

          {/* 검색어 + 카테고리 */}
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="공고명 검색 (예: 정보시스템, 홈페이지 구축)"
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-kira-500"
            />
            <select
              value={searchCategory}
              onChange={(e) => setSearchCategory(e.target.value)}
              className="rounded-lg border border-slate-200 px-2 py-2 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-kira-500"
            >
              <option value="all">전체</option>
              <option value="service">용역</option>
              <option value="goods">물품</option>
              <option value="construction">공사</option>
              <option value="foreign">외자</option>
            </select>
            <Button onClick={() => handleSearch()} size="sm" disabled={searching}>
              {searching ? <Loader2 size={14} className="animate-spin" /> : '검색'}
            </Button>
          </div>

          {/* 고급 필터 토글 */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 mb-2"
          >
            {showFilters ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            <span>상세 필터</span>
            {activeFilterCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full bg-kira-100 text-kira-700 text-[10px] font-semibold">
                {activeFilterCount}
              </span>
            )}
          </button>

          {/* 고급 필터 패널 */}
          {showFilters && (
            <div className="grid grid-cols-2 gap-2 mb-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              {/* 지역 */}
              <div>
                <label className="block text-[11px] font-medium text-slate-500 mb-1">지역</label>
                <select
                  value={filterRegionCode}
                  onChange={(e) => setFilterRegionCode(e.target.value)}
                  className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-kira-500"
                >
                  {REGION_OPTIONS.map((r) => (
                    <option key={r.code} value={r.code}>{r.label}</option>
                  ))}
                </select>
              </div>

              {/* 기간 */}
              <div>
                <label className="block text-[11px] font-medium text-slate-500 mb-1">조회 기간</label>
                <select
                  value={filterPeriod}
                  onChange={(e) => setFilterPeriod(e.target.value)}
                  className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-kira-500"
                >
                  <option value="1w">최근 1주</option>
                  <option value="1m">최근 1개월</option>
                  <option value="3m">최근 3개월</option>
                  <option value="6m">최근 6개월</option>
                  <option value="12m">최근 1년</option>
                </select>
              </div>

              {/* 금액 범위 */}
              <div>
                <label className="block text-[11px] font-medium text-slate-500 mb-1">추정가격 (만원)</label>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    value={filterMinAmt}
                    onChange={(e) => setFilterMinAmt(e.target.value)}
                    placeholder="최소"
                    className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-kira-500"
                  />
                  <span className="text-xs text-slate-400">~</span>
                  <input
                    type="number"
                    value={filterMaxAmt}
                    onChange={(e) => setFilterMaxAmt(e.target.value)}
                    placeholder="최대"
                    className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-kira-500"
                  />
                </div>
              </div>

              {/* 업종 */}
              <div>
                <label className="block text-[11px] font-medium text-slate-500 mb-1">업종</label>
                <input
                  type="text"
                  value={filterIndustry}
                  onChange={(e) => setFilterIndustry(e.target.value)}
                  placeholder="예: 소프트웨어"
                  className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-kira-500"
                />
              </div>

              {/* 입찰마감 제외 */}
              <div className="col-span-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="bidCloseExcl"
                  checked={filterBidCloseExcl}
                  onChange={(e) => setFilterBidCloseExcl(e.target.checked)}
                  className="rounded border-slate-300 text-kira-600 focus:ring-kira-500"
                />
                <label htmlFor="bidCloseExcl" className="text-xs text-slate-600">
                  마감된 공고 제외 (진행중인 공고만 표시)
                </label>
              </div>

              {/* 필터 초기화 */}
              <div className="col-span-2 flex justify-end">
                <button
                  onClick={() => {
                    setFilterRegionCode('');
                    setFilterMinAmt('');
                    setFilterMaxAmt('');
                    setFilterPeriod('1m');
                    setFilterIndustry('');
                    setFilterBidCloseExcl(true);
                  }}
                  className="text-[11px] text-slate-400 hover:text-slate-600"
                >
                  필터 초기화
                </button>
              </div>
            </div>
          )}

          {/* Search results */}
          {hasSearched && (
            <>
              <p className="text-xs text-slate-500 mb-2">
                {searchTotal > 0 ? `${searchTotal}건 중 ${(searchPage - 1) * 10 + 1}-${Math.min(searchPage * 10, searchTotal)}건` : '검색 결과가 없습니다'}
              </p>
              <div className="space-y-2 max-h-[480px] overflow-y-auto">
                {searchResults.map((bid) => (
                  <div
                    key={bid.id}
                    className="rounded-lg border border-slate-100 bg-slate-50 p-3 hover:border-kira-300 hover:bg-kira-50/30 transition-colors"
                  >
                    {/* Title row */}
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <p className="text-sm font-medium text-slate-800 line-clamp-2 flex-1">{bid.title}</p>
                      <div className="flex items-center gap-1 shrink-0">
                        {(bid.detailUrl || bid.url) && (
                          <a
                            href={bid.detailUrl || bid.url || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1 text-slate-400 hover:text-kira-600"
                            title="나라장터에서 보기"
                          >
                            <ExternalLink size={14} />
                          </a>
                        )}
                      </div>
                    </div>

                    {/* Info row */}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-2">
                      <span className="text-xs text-slate-500">{bid.issuingOrg}</span>
                      {bid.demandOrg && bid.demandOrg !== bid.issuingOrg && (
                        <span className="text-xs text-slate-400">{bid.demandOrg}</span>
                      )}
                      <span className="text-xs font-medium text-slate-700">
                        {formatPrice(bid.estimatedPrice)}
                      </span>
                      {bid.contractMethod && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">
                          {bid.contractMethod}
                        </span>
                      )}
                      <span className={`text-xs font-medium ${
                        bid.deadlineAt && new Date(bid.deadlineAt) < new Date()
                          ? 'text-red-500'
                          : bid.deadlineAt && (new Date(bid.deadlineAt).getTime() - Date.now()) < 3 * 24 * 60 * 60 * 1000
                            ? 'text-amber-600'
                            : 'text-slate-500'
                      }`}>
                        {formatDeadline(bid.deadlineAt)}
                      </span>
                      {bid.category && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-kira-50 text-kira-600">
                          {bid.category}
                        </span>
                      )}
                    </div>

                    {/* Attachments */}
                    {bid.attachments && bid.attachments.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 mb-2">
                        {bid.attachments.slice(0, 3).map((att, i) => (
                          <a
                            key={i}
                            href={att.fileUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] text-blue-600 hover:text-blue-800 bg-blue-50 px-1.5 py-0.5 rounded"
                            title={att.fileNm}
                          >
                            <FileText size={10} />
                            <span className="max-w-[120px] truncate">{att.fileNm}</span>
                          </a>
                        ))}
                        {bid.attachments.length > 3 && (
                          <span className="text-[10px] text-slate-400">+{bid.attachments.length - 3}개</span>
                        )}
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleSelectBid(bid)}
                        className="px-2.5 py-1 text-xs font-medium text-kira-700 bg-kira-100 rounded-md hover:bg-kira-200 transition-colors"
                      >
                        선택
                      </button>
                      <button
                        onClick={() => handleSelectAndAnalyze(bid)}
                        disabled={analyzing}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-kira-600 rounded-md hover:bg-kira-700 disabled:opacity-50 transition-colors"
                      >
                        <Zap size={10} />
                        바로 분석
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              {/* Pagination */}
              {searchTotal > 10 && (
                <div className="flex justify-center gap-2 mt-3">
                  <button
                    onClick={() => handleSearch(searchPage - 1)}
                    disabled={searchPage <= 1 || searching}
                    className="px-3 py-1 text-xs rounded-md border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
                  >
                    이전
                  </button>
                  <span className="px-3 py-1 text-xs text-slate-500">
                    {searchPage} / {Math.ceil(searchTotal / 10)}
                  </span>
                  <button
                    onClick={() => handleSearch(searchPage + 1)}
                    disabled={searchPage >= Math.ceil(searchTotal / 10) || searching}
                    className="px-3 py-1 text-xs rounded-md border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
                  >
                    다음
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 flex items-start gap-2">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          <span className="flex-1">{error}</span>
          <button
            onClick={() => setError('')}
            className="text-red-400 hover:text-red-600 shrink-0"
            aria-label="닫기"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Classify action */}
      {hasSnapshot && (
        <Button onClick={handleClassify} disabled={classifying} size="sm" variant="secondary">
          {classifying ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              <span className="ml-1">분류 중...</span>
            </>
          ) : (
            '제출 패키지 분류 실행'
          )}
        </Button>
      )}
    </div>
  );
}
