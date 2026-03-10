import React, { useEffect, useState, useCallback, useRef } from 'react';
import { ClipboardList, Download, FileSearch } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import MarkdownViewer from '../../common/MarkdownViewer';
import type { AnalysisPayload } from '../../../types';

const LS_KEY = 'kira_last_analysis';
const LS_FILE_KEY = 'kira_last_analysis_file_url';

export default function RfpViewer() {
  const [analysis, setAnalysis] = useState<AnalysisPayload | null>(null);
  const [fileUrl, setFileUrl] = useState('');
  const [loading, setLoading] = useState(true);
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

  const loadAnalysis = useCallback(() => {
    setLoading(true);
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as AnalysisPayload;
        setAnalysis(parsed);
      }
      const url = localStorage.getItem(LS_FILE_KEY) || '';
      setFileUrl(url);
    } catch {
      if (mountedRef.current) showToast('분석 데이터 로드 실패', 'error');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { loadAnalysis(); }, [loadAnalysis]);

  if (loading) {
    return <div className="text-center text-slate-400 py-12">RFP 분석결과 로드 중...</div>;
  }

  if (!analysis) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
        <FileSearch size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-500">분석된 RFP 문서가 없습니다.</p>
        <p className="text-xs text-slate-400 mt-1">채팅에서 공고를 검색하거나 문서를 업로드하여 분석해주세요.</p>
      </div>
    );
  }

  const infoItems = [
    { label: '공고명', value: analysis.title },
    { label: '발주기관', value: analysis.issuing_org },
    { label: '공고번호', value: analysis.announcement_number },
    { label: '마감일', value: analysis.deadline },
    { label: '사업기간', value: analysis.project_period },
    { label: '예산', value: analysis.budget },
  ].filter(item => item.value);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardList size={20} className="text-kira-600" />
          <h2 className="text-lg font-semibold text-slate-900">RFP 분석결과</h2>
          <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-600">
            분석 완료
          </span>
        </div>
        {fileUrl && (
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
          >
            <Download size={14} /> 원본 다운로드
          </a>
        )}
      </div>

      {/* Summary info card */}
      {infoItems.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">공고 개요</h3>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            {infoItems.map((item) => (
              <div key={item.label}>
                <dt className="text-xs text-slate-500">{item.label}</dt>
                <dd className="text-sm font-medium text-slate-800 mt-0.5">{item.value}</dd>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Requirements table */}
      {analysis.requirements && analysis.requirements.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">
            자격 요건 ({analysis.requirements.length}건)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 rounded-md">
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">분류</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">요건 설명</th>
                  <th className="px-3 py-2 text-center text-xs font-semibold text-slate-500">필수</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {analysis.requirements.map((req, i) => (
                  <tr key={i} className="hover:bg-slate-50/50">
                    <td className="px-3 py-2.5 text-xs text-slate-600 whitespace-nowrap">{req.category}</td>
                    <td className="px-3 py-2.5 text-xs text-slate-800">{req.description}</td>
                    <td className="px-3 py-2.5 text-center">
                      <span
                        className={`inline-block w-2 h-2 rounded-full ${
                          req.is_mandatory ? 'bg-red-500' : 'bg-slate-300'
                        }`}
                        title={req.is_mandatory ? '필수' : '선택'}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Evaluation criteria */}
      {analysis.evaluation_criteria && analysis.evaluation_criteria.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">
            평가 기준 ({analysis.evaluation_criteria.length}건)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 rounded-md">
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">분류</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">항목</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold text-slate-500">배점</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {analysis.evaluation_criteria.map((crit, i) => (
                  <tr key={i} className="hover:bg-slate-50/50">
                    <td className="px-3 py-2.5 text-xs text-slate-600 whitespace-nowrap">{crit.category}</td>
                    <td className="px-3 py-2.5 text-xs text-slate-800">{crit.item}</td>
                    <td className="px-3 py-2.5 text-right text-xs font-medium text-kira-600">{crit.score}점</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* RFP Summary */}
      {analysis.rfp_summary && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">RFP 요약</h3>
          <MarkdownViewer content={analysis.rfp_summary} />
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
