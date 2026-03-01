import React, { useState, useEffect } from 'react';
import { ExternalLink, FileDown, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import type { BidCardListMessage, MessageAction } from '../../../types';

interface Props {
  message: BidCardListMessage;
  onAction: (action: MessageAction) => void;
}

const BidCardListView: React.FC<Props> = ({ message, onAction }) => {
  const [localSelected, setLocalSelected] = useState<Set<string>>(
    new Set(message.selectedIds ?? []),
  );
  const isSubmitted = Boolean(message.selectedIds);

  // Reset selection when page/cards change
  const page = message.page ?? 1;
  useEffect(() => {
    if (!isSubmitted) setLocalSelected(new Set());
  }, [page, isSubmitted]);

  const toggleBid = (id: string) => {
    if (isSubmitted) return;
    setLocalSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleEvaluate = () => {
    const ids = Array.from(localSelected);
    if (ids.length === 0) return;
    onAction({ type: 'bid_selected', bidIds: ids, messageId: message.id });
  };

  const currentPage = message.page ?? 1;
  const totalCount = message.total ?? message.cards.length;
  const pageSize = message.pageSize ?? 20;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  const handlePageChange = (newPage: number) => {
    if (!message.searchConditions) return;
    onAction({
      type: 'search_page',
      page: newPage,
      conditions: message.searchConditions,
      messageId: message.id,
    });
  };

  const handleExportCsv = () => {
    const rows = message.cards.map((bid, idx) => [
      idx + 1 + (currentPage - 1) * pageSize,
      bid.category ?? '',
      bid.title,
      bid.issuingOrg ?? '',
      bid.deadlineAt ? bid.deadlineAt.slice(0, 10) : '',
      bid.estimatedPrice ?? '',
    ]);
    const header = ['No', '업무구분', '공고명', '공고기관', '마감일', '추정가격'];
    const csv = [header, ...rows].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '공고검색결과.csv';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 200);
  };

  return (
    <div>
      <p className="mb-3 text-sm font-medium">{message.text}</p>

      {/* 테이블 */}
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              {!isSubmitted && <th className="w-8 px-3 py-2"><span className="sr-only">선택</span></th>}
              <th className="w-10 px-3 py-2">No</th>
              <th className="w-16 px-3 py-2">구분</th>
              <th className="px-3 py-2">공고명</th>
              <th className="w-28 px-3 py-2">공고기관</th>
              <th className="w-24 px-3 py-2">마감일</th>
              <th className="w-20 px-3 py-2 text-center">분석</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {message.cards.map((bid, idx) => {
              const checked = localSelected.has(bid.id);
              const deadlineStr = bid.deadlineAt ? bid.deadlineAt.slice(0, 10) : '-';
              const isExpired = bid.deadlineAt ? new Date(bid.deadlineAt) < new Date() : false;

              return (
                <tr
                  key={bid.id}
                  className={`transition-colors ${checked ? 'bg-kira-50' : isExpired ? 'bg-slate-50/60 opacity-70 hover:opacity-100' : 'hover:bg-slate-50'}`}
                >
                  {!isSubmitted && (
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleBid(bid.id)}
                        className="rounded"
                      />
                    </td>
                  )}
                  <td className="px-3 py-2 text-slate-500">{idx + 1 + (currentPage - 1) * pageSize}</td>
                  <td className="px-3 py-2">
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
                      {bid.category ?? '-'}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      <span className="text-slate-800 font-medium leading-snug line-clamp-2">{bid.title}</span>
                      {bid.url && (
                        <a
                          href={bid.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="shrink-0 text-slate-400 hover:text-kira-600"
                          title="공고 원문"
                        >
                          <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                    {bid.demandOrg && (
                      <p className="mt-0.5 text-[11px] text-slate-400">수요기관: {bid.demandOrg}</p>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-500">{bid.issuingOrg ?? '-'}</td>
                  <td className="px-3 py-2 text-xs">
                    <div className="flex items-center gap-1">
                      <span className={isExpired ? 'text-slate-400 line-through' : 'text-slate-600'}>
                        {deadlineStr}
                      </span>
                      {isExpired && (
                        <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-600">
                          마감
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAction({ type: 'analyze_bid', bid, messageId: message.id });
                      }}
                      className="inline-flex items-center gap-1 rounded bg-kira-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-kira-700"
                    >
                      <Search size={11} />
                      분석
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && message.searchConditions && (
        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
          <span>전체 {totalCount}건 (페이지 {currentPage}/{totalPages})</span>
          <div className="flex gap-1">
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => handlePageChange(currentPage - 1)}
              className="rounded border border-slate-300 p-1 hover:bg-slate-100 disabled:opacity-30"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              type="button"
              disabled={currentPage >= totalPages}
              onClick={() => handlePageChange(currentPage + 1)}
              className="rounded border border-slate-300 p-1 hover:bg-slate-100 disabled:opacity-30"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* 하단 버튼 */}
      {!isSubmitted && (
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={handleEvaluate}
            disabled={localSelected.size === 0}
            className="flex-1 rounded-lg bg-kira-700 px-4 py-2 text-sm font-medium text-white hover:bg-kira-800 disabled:opacity-50"
          >
            선택 공고 평가 ({localSelected.size})
          </button>
          <button
            type="button"
            onClick={handleExportCsv}
            className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            <FileDown size={14} /> CSV
          </button>
        </div>
      )}
    </div>
  );
};

export default BidCardListView;
