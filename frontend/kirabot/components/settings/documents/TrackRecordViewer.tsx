import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Award, Download, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { generateTrackRecord, getFileDownloadUrl } from '../../../services/kiraApiService';
import type { TrackRecordDocResponse } from '../../../services/kiraApiService';
import { useDocumentHistory } from '../../../hooks/useDocumentHistory';
import DocumentHistorySelect from '../../common/DocumentHistorySelect';

function isValidTrackRecordResponse(data: unknown): data is TrackRecordDocResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return typeof d.track_record_count === 'number' && typeof d.personnel_count === 'number';
}

export default function TrackRecordViewer() {
  const { entries, selected, selectedId, setSelectedId, push, remove, loading } = useDocumentHistory<TrackRecordDocResponse>(
    'kira_last_track_record',
    isValidTrackRecordResponse,
  );
  const data = selected?.data ?? null;

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
    const sessionId = localStorage.getItem('kira_session_id') || '';
    if (!sessionId) {
      showToast('세션이 없습니다. 먼저 문서를 분석해주세요.', 'error');
      return;
    }

    setRegenerating(true);
    try {
      const result = await generateTrackRecord(sessionId);
      if (!mountedRef.current) return;
      push(result, '실적기술서');
      showToast('실적기술서가 재생성되었습니다.');
    } catch (e) {
      showToast(e instanceof Error ? e.message : '실적기술서 재생성 실패', 'error');
    } finally {
      if (mountedRef.current) setRegenerating(false);
    }
  };

  if (loading) {
    return <div className="text-center text-slate-400 py-12">실적기술서 데이터 로드 중...</div>;
  }

  if (!data) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
        <Award size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-500">생성된 실적/경력 기술서가 없습니다.</p>
        <p className="text-xs text-slate-400 mt-1">채팅에서 공고를 분석한 후 '실적기술서 생성' 버튼을 눌러주세요.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Award size={20} className="text-kira-600" />
          <h2 className="text-lg font-semibold text-slate-900">실적/경력 기술서</h2>
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
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-kira-600">{data.track_record_count}</div>
          <div className="text-xs text-slate-500 mt-1">실적 건수</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-kira-600">{data.personnel_count}</div>
          <div className="text-xs text-slate-500 mt-1">투입인력</div>
        </div>
      </div>

      {/* Download card */}
      {data.docx_filename && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">다운로드</h3>
          <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/50 p-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-kira-50">
                <Award size={18} className="text-kira-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">{data.docx_filename}</p>
                <p className="text-xs text-slate-500">실적/경력 기술서 (DOCX)</p>
              </div>
            </div>
            <a
              href={getFileDownloadUrl(data.docx_filename)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
            >
              <Download size={14} /> 다운로드
            </a>
          </div>
        </div>
      )}

      {/* Empty company DB notice */}
      {data.track_record_count === 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm text-amber-700">
            회사 DB에 실적/인력 정보가 없습니다. 설정 &gt; 회사 정보에서 실적과 인력을 등록하면 맞춤 기술서가 생성됩니다.
          </p>
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
