import React, { useEffect, useCallback, useRef, useState } from 'react';
import { Presentation, Download, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { generatePpt, getFileDownloadUrl } from '../../../services/kiraApiService';
import type { PptResponse } from '../../../services/kiraApiService';
import { useDocumentHistory } from '../../../hooks/useDocumentHistory';
import DocumentHistorySelect from '../../common/DocumentHistorySelect';

function isValidPptResponse(data: unknown): data is PptResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return typeof d.slide_count === 'number' && typeof d.generation_time_sec === 'number';
}

export default function PptViewer() {
  const { entries, selected, selectedId, setSelectedId, push, remove, loading } = useDocumentHistory<PptResponse>(
    'kira_last_ppt',
    isValidPptResponse,
  );
  const ppt = selected?.data ?? null;

  const [regenerating, setRegenerating] = useState(false);
  const [toast, setToast] = useState('');
  const [toastType, setToastType] = useState<'success' | 'error'>('success');
  const mountedRef = useRef(true);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  const showToast = useCallback((msg: string, type: 'success' | 'error' = 'success') => {
    setToast(msg);
    setToastType(type);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => { if (mountedRef.current) setToast(''); }, 3000);
  }, []);

  const handleRegenerate = async () => {
    const sessionId = sessionStorage.getItem('kira_session_id') || '';
    if (!sessionId) {
      showToast('세션이 없습니다. 먼저 문서를 분석해주세요.', 'error');
      return;
    }

    setRegenerating(true);
    try {
      const companyId = sessionStorage.getItem('kira_company_id') || '_default';
      const result = await generatePpt(sessionId, 30, 10, companyId);
      if (!mountedRef.current) return;
      push(result, 'PPT 발표자료');
      showToast('PPT가 재생성되었습니다.');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'PPT 재생성 실패', 'error');
    } finally {
      if (mountedRef.current) setRegenerating(false);
    }
  };

  if (loading) {
    return <div className="text-center text-slate-400 py-12">PPT 데이터 로드 중...</div>;
  }

  if (!ppt) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
        <Presentation size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-500">생성된 PPT 발표자료가 없습니다.</p>
        <p className="text-xs text-slate-400 mt-1">채팅에서 공고를 분석한 후 'PPT 생성' 버튼을 눌러주세요.</p>
      </div>
    );
  }

  const qnaPairs = ppt.qna_pairs ?? [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Presentation size={20} className="text-kira-600" />
          <h2 className="text-lg font-semibold text-slate-900">PPT 발표자료</h2>
          <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-600">
            생성 완료
          </span>
        </div>
        <div className="flex items-center gap-2">
          <DocumentHistorySelect
            entries={entries}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onRemove={remove}
          />
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={regenerating}
            className="flex items-center gap-1 rounded-lg bg-kira-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-kira-700 disabled:opacity-50"
          >
            <RefreshCw size={14} className={regenerating ? 'animate-spin' : ''} />
            {regenerating ? '재생성 중...' : '재생성'}
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-kira-600">{ppt.slide_count}</div>
          <div className="text-xs text-slate-500 mt-1">슬라이드</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-kira-600">{ppt.total_duration_min}분</div>
          <div className="text-xs text-slate-500 mt-1">발표시간</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-kira-600">{qnaPairs.length}</div>
          <div className="text-xs text-slate-500 mt-1">예상질문</div>
        </div>
      </div>

      {/* Download card */}
      {ppt.pptx_filename && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">다운로드</h3>
          <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/50 p-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-kira-50">
                <Presentation size={18} className="text-kira-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">{ppt.pptx_filename}</p>
                <p className="text-xs text-slate-500">PowerPoint 발표자료 (PPTX)</p>
              </div>
            </div>
            <a
              href={getFileDownloadUrl(ppt.pptx_filename)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
            >
              <Download size={14} /> 다운로드
            </a>
          </div>
        </div>
      )}

      {/* QnA section */}
      {qnaPairs.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-4">
            예상질문 &amp; 모범답변 ({qnaPairs.length}개)
          </h3>
          <div className="space-y-4">
            {qnaPairs.map((pair, i) => (
              <div key={i} className="rounded-lg border border-slate-100 bg-slate-50/30 p-4">
                {/* Question */}
                <div className="flex items-start gap-2 mb-3">
                  <span className="shrink-0 rounded bg-blue-100 px-1.5 py-0.5 text-xs font-bold text-blue-600">
                    Q{i + 1}
                  </span>
                  {pair.category && (
                    <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                      {pair.category}
                    </span>
                  )}
                  <p className="text-sm text-slate-800 leading-relaxed">{pair.question}</p>
                </div>
                {/* Answer */}
                <div className="flex items-start gap-2 pl-1">
                  <span className="shrink-0 rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-bold text-emerald-600">
                    A{i + 1}
                  </span>
                  <p className="text-sm text-slate-600 leading-relaxed">{pair.answer}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl border shadow-lg px-5 py-3 text-sm ${
              toastType === 'error'
                ? 'border-red-200 bg-red-50 text-red-700'
                : 'border-emerald-200 bg-emerald-50 text-emerald-700'
            }`}
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
