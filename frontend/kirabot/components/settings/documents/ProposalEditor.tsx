import React, { useEffect, useState, useCallback, useRef, Suspense, lazy } from 'react';
import { FileText, RefreshCw, Download, Pencil, Save, X } from 'lucide-react';
import { motion } from 'framer-motion';
import MarkdownViewer from '../../common/MarkdownViewer';

const MarkdownEditor = lazy(() => import('../../common/MarkdownEditor'));
import {
  getProposalSections,
  updateProposalSection,
  reassembleProposal,
  getProposalDownloadUrl,
} from '../../../services/kiraApiService';
import type { ProposalSectionData } from '../../../types';

export default function ProposalEditor() {
  const [sections, setSections] = useState<ProposalSectionData[]>([]);
  const [title, setTitle] = useState('');
  const [docxFilename, setDocxFilename] = useState('');
  const [loading, setLoading] = useState(true);
  const [reassembling, setReassembling] = useState(false);
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

  const loadSections = useCallback(async () => {
    const fn = localStorage.getItem('kira_last_proposal') || '';
    if (!fn) {
      setLoading(false);
      return;
    }
    setDocxFilename(fn);
    setLoading(true);
    try {
      const data = await getProposalSections(fn);
      if (!mountedRef.current) return;
      setSections(data.sections);
      setTitle(data.title || '');
    } catch {
      if (!mountedRef.current) return;
      // 404 = no sections saved yet, that's OK
      setSections([]);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => { loadSections(); }, [loadSections]);

  const handleSaveSection = async (sectionName: string, text: string) => {
    try {
      await updateProposalSection(docxFilename, sectionName, text);
      showToast('저장되었습니다.');
      // Update local state
      setSections(prev => prev.map(s => s.name === sectionName ? { ...s, text } : s));
    } catch (e) {
      showToast(e instanceof Error ? e.message : '저장 실패', 'error');
      throw e;
    }
  };

  const handleReassemble = async () => {
    setReassembling(true);
    try {
      const result = await reassembleProposal(docxFilename);
      if (result.docx_filename) {
        setDocxFilename(result.docx_filename);
        try { localStorage.setItem('kira_last_proposal', result.docx_filename); } catch { /* noop */ }
      }
      showToast('DOCX가 재생성되었습니다.');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'DOCX 재생성 실패', 'error');
    } finally {
      setReassembling(false);
    }
  };

  if (loading) {
    return <div className="text-center text-slate-400 py-12">제안서 로드 중...</div>;
  }

  if (!docxFilename || sections.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
        <FileText size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-500">아직 생성된 제안서가 없습니다.</p>
        <p className="text-xs text-slate-400 mt-1">채팅에서 공고를 분석한 후 '제안서 생성' 버튼을 눌러주세요.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText size={20} className="text-kira-600" />
          <h2 className="text-lg font-semibold text-slate-900">제안서 섹션 편집</h2>
          {title && <span className="text-xs text-slate-400 truncate max-w-xs">{title}</span>}
        </div>
        <div className="flex items-center gap-2">
          <a
            href={getProposalDownloadUrl(docxFilename)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-kira-600"
          >
            <Download size={14} /> DOCX 다운로드
          </a>
          <button
            onClick={handleReassemble}
            disabled={reassembling}
            className="flex items-center gap-1 rounded-lg bg-kira-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-kira-700 disabled:opacity-50"
          >
            <RefreshCw size={14} className={reassembling ? 'animate-spin' : ''} />
            {reassembling ? '재생성 중...' : 'DOCX 재생성'}
          </button>
        </div>
      </div>

      {sections.map((s) => (
        <ProposalSectionCard
          key={s.name}
          name={s.name}
          text={s.text}
          onSave={handleSaveSection}
        />
      ))}

      {toast && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl border shadow-lg px-5 py-3 text-sm ${
            toastType === 'error'
              ? 'border-red-200 bg-red-50 text-red-700'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700'
          }`}
        >
          {toast}
        </motion.div>
      )}
    </div>
  );
}

// ── Section card with WYSIWYG editing ──

interface SectionCardProps {
  name: string;
  text: string;
  onSave: (name: string, text: string) => Promise<void>;
}

function ProposalSectionCard({ name, text, onSave }: SectionCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(text);
  }, [text, editing]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(name, draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setDraft(text);
    setEditing(false);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold text-slate-800">{name}</h3>
        {!editing && (
          <button onClick={() => setEditing(true)} className="text-slate-400 hover:text-kira-600 p-1" title="편집">
            <Pencil size={16} />
          </button>
        )}
      </div>

      {editing ? (
        <div className="space-y-3">
          <Suspense fallback={<div className="text-xs text-slate-400 py-4 text-center">에디터 로딩 중...</div>}>
            <MarkdownEditor value={draft} onChange={setDraft} />
          </Suspense>
          <div className="flex gap-2 justify-end">
            <button onClick={handleCancel} className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
              <X size={14} /> 취소
            </button>
            <button onClick={handleSave} disabled={saving} className="flex items-center gap-1 rounded-lg bg-kira-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-kira-700 disabled:opacity-50">
              <Save size={14} /> {saving ? '저장 중...' : '저장'}
            </button>
          </div>
        </div>
      ) : (
        <MarkdownViewer content={text} />
      )}
    </div>
  );
}
