import React, { useEffect, useState, useCallback, useRef } from 'react';
import { CalendarDays, Download, RefreshCw, Table2, BarChart3, FileText } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { generateWbs, getFileDownloadUrl } from '../../../services/kiraApiService';
import type { WbsResponse } from '../../../services/kiraApiService';
import { useDocumentHistory } from '../../../hooks/useDocumentHistory';
import DocumentHistorySelect from '../../common/DocumentHistorySelect';

function isValidWbsResponse(data: unknown): data is WbsResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return typeof d.tasks_count === 'number' && typeof d.total_months === 'number';
}

export default function WbsViewer() {
  const { entries, selected, selectedId, setSelectedId, push, remove, loading } = useDocumentHistory<WbsResponse>(
    'kira_last_wbs',
    isValidWbsResponse,
  );
  const wbs = selected?.data ?? null;

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
      const usePack = localStorage.getItem('kira_use_pack') === 'true';
      const companyId = localStorage.getItem('kira_company_id') || '_default';
      const result = await generateWbs(sessionId, undefined, usePack, companyId);
      if (!mountedRef.current) return;
      push(result, '수행계획서');
      showToast('WBS가 재생성되었습니다.');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'WBS 재생성 실패', 'error');
    } finally {
      if (mountedRef.current) setRegenerating(false);
    }
  };

  if (loading) {
    return <div className="text-center text-slate-400 py-12">WBS 데이터 로드 중...</div>;
  }

  if (!wbs) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
        <CalendarDays size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-500">생성된 WBS 수행계획서가 없습니다.</p>
        <p className="text-xs text-slate-400 mt-1">채팅에서 공고를 분석한 후 'WBS 생성' 버튼을 눌러주세요.</p>
      </div>
    );
  }

  const fileCards = [
    {
      icon: Table2,
      name: wbs.xlsx_filename,
      label: 'WBS Excel',
      description: 'WBS 태스크 목록 (XLSX)',
    },
    {
      icon: BarChart3,
      name: wbs.gantt_filename,
      label: '간트차트',
      description: '프로젝트 일정 시각화 (PNG)',
    },
    {
      icon: FileText,
      name: wbs.docx_filename,
      label: '수행계획서',
      description: '수행계획서 문서 (DOCX)',
    },
  ].filter((card): card is typeof card & { name: string } => Boolean(card.name));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays size={20} className="text-kira-600" />
          <h2 className="text-lg font-semibold text-slate-900">WBS 수행계획서</h2>
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
          <div className="text-2xl font-bold text-kira-600">{wbs.tasks_count}</div>
          <div className="text-xs text-slate-500 mt-1">WBS 태스크</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-kira-600">{wbs.total_months}</div>
          <div className="text-xs text-slate-500 mt-1">수행기간 (개월)</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-kira-600">{wbs.generation_time_sec}s</div>
          <div className="text-xs text-slate-500 mt-1">생성 시간</div>
        </div>
      </div>

      {/* Methodology detection */}
      {wbs.methodology && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">방법론 감지</h3>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600">감지된 방법론:</span>
            <span className="rounded-full bg-kira-50 border border-kira-200 px-3 py-0.5 text-xs font-semibold text-kira-700 capitalize">
              {wbs.methodology === 'waterfall' ? 'Waterfall (폭포수)' :
               wbs.methodology === 'agile' ? 'Agile (애자일)' :
               wbs.methodology === 'hybrid' ? 'Hybrid (하이브리드)' :
               wbs.methodology}
            </span>
          </div>
        </div>
      )}

      {/* Task preview table */}
      {wbs.tasks && wbs.tasks.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">주요 태스크 미리보기</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50">
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500 w-8">#</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">태스크명</th>
                  <th className="px-3 py-2 text-center text-xs font-semibold text-slate-500">기간</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">담당</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {wbs.tasks.slice(0, 5).map((task, i) => (
                  <tr key={i} className="hover:bg-slate-50/50">
                    <td className="px-3 py-2.5 text-xs text-slate-400">{i + 1}</td>
                    <td className="px-3 py-2.5 text-xs text-slate-800">{task.task_name}</td>
                    <td className="px-3 py-2.5 text-center text-xs text-slate-600">
                      {(task.start_month != null && task.duration_months != null)
                        ? `M${task.start_month}~M${task.start_month + Math.max(1, task.duration_months) - 1}`
                        : '-'}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-slate-600">{task.responsible_role || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {wbs.tasks.length > 5 && (
            <p className="text-xs text-slate-400 text-center mt-2">
              외 {wbs.tasks.length - 5}개 태스크
            </p>
          )}
        </div>
      )}

      {/* Download cards */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="text-base font-semibold text-slate-800 mb-3">다운로드</h3>
        <div className="space-y-3">
          {fileCards.map((card) => {
            const Icon = card.icon;
            return (
              <div
                key={card.name}
                className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/50 p-3"
              >
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-kira-50">
                    <Icon size={18} className="text-kira-600" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-800">{card.label}</p>
                    <p className="text-xs text-slate-500">{card.description}</p>
                  </div>
                </div>
                <a
                  href={getFileDownloadUrl(card.name)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                >
                  <Download size={14} /> 다운로드
                </a>
              </div>
            );
          })}
        </div>
      </div>

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
