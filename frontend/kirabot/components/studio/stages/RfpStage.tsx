import React, { useState } from 'react';
import { Search, Upload, Loader2, CheckCircle2, X, ExternalLink, AlertCircle } from 'lucide-react';
import Button from '../../Button';
import type { StudioProject } from '../../../services/studioApi';
import { searchNaraBids, type NaraBidNotice } from '../../../services/studioApi';

const MAX_UPLOAD_SIZE_MB = 20;
const ALLOWED_EXTENSIONS = new Set(['.pdf', '.docx', '.hwp', '.hwpx', '.txt', '.xlsx', '.pptx']);

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
    if (!searchKeyword.trim()) return;
    setSearching(true);
    setError('');
    try {
      const result = await searchNaraBids({
        keywords: searchKeyword.trim(),
        category: searchCategory,
        page,
      });
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
    // Format bid info as RFP text for analysis
    const lines = [
      `[공고명] ${bid.title}`,
      `[발주기관] ${bid.issuingOrg}`,
      bid.region ? `[지역] ${bid.region}` : '',
      bid.estimatedPrice ? `[추정가격] ${bid.estimatedPrice}` : '',
      bid.deadlineAt ? `[마감일] ${bid.deadlineAt}` : '',
      bid.category ? `[분류] ${bid.category}` : '',
      bid.awardMethod ? `[낙찰방식] ${bid.awardMethod}` : '',
      bid.url ? `[공고URL] ${bid.url}` : '',
    ].filter(Boolean).join('\n');
    setRfpText(lines);
    setShowSearch(false);
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
    return dateStr;
  };

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

          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="검색어 입력 (예: 정보시스템, 홈페이지 구축)"
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
            <Button onClick={() => handleSearch()} size="sm" disabled={searching || !searchKeyword.trim()}>
              {searching ? <Loader2 size={14} className="animate-spin" /> : '검색'}
            </Button>
          </div>

          {/* Search results */}
          {hasSearched && (
            <>
              <p className="text-xs text-slate-500 mb-2">
                {searchTotal > 0 ? `${searchTotal}건 중 ${(searchPage - 1) * 10 + 1}-${Math.min(searchPage * 10, searchTotal)}건` : '검색 결과가 없습니다'}
              </p>
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {searchResults.map((bid) => (
                  <div
                    key={bid.id}
                    className="rounded-lg border border-slate-100 bg-slate-50 p-3 hover:border-kira-300 hover:bg-kira-50/30 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">{bid.title}</p>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-xs text-slate-500">{bid.issuingOrg}</span>
                          <span className="text-xs text-slate-400">{bid.estimatedPrice || '-'}</span>
                          <span className={`text-xs ${bid.deadlineAt && new Date(bid.deadlineAt) < new Date() ? 'text-red-500' : 'text-slate-500'}`}>
                            {formatDeadline(bid.deadlineAt)}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {bid.url && (
                          <a
                            href={bid.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1 text-slate-400 hover:text-kira-600"
                            title="나라장터에서 보기"
                          >
                            <ExternalLink size={14} />
                          </a>
                        )}
                        <button
                          onClick={() => handleSelectBid(bid)}
                          className="px-2 py-1 text-xs font-medium text-kira-700 bg-kira-100 rounded-md hover:bg-kira-200 transition-colors"
                        >
                          선택
                        </button>
                      </div>
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
