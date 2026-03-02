import React, { useState, useEffect, Suspense, lazy } from 'react';
import { Pencil, Save, X, History } from 'lucide-react';
import MarkdownViewer from '../../common/MarkdownViewer';

const MarkdownEditor = lazy(() => import('../../common/MarkdownEditor'));

interface Props {
  name: string;
  content: string;
  editable: boolean;
  onSave: (name: string, content: string) => Promise<void>;
  onShowHistory?: () => void;
}

export default function ProfileSection({ name, content, editable, onSave, onShowHistory }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const [saving, setSaving] = useState(false);

  // Sync draft with external content changes (e.g. after rollback or reload)
  useEffect(() => {
    if (!editing) setDraft(content);
  }, [content, editing]);

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
    setDraft(content);
    setEditing(false);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold text-slate-800">## {name}</h3>
        <div className="flex items-center gap-1.5">
          {onShowHistory && (
            <button onClick={onShowHistory} className="text-slate-400 hover:text-slate-600 p-1" title="버전 이력">
              <History size={16} />
            </button>
          )}
          {editable && !editing && (
            <button onClick={() => setEditing(true)} className="text-slate-400 hover:text-kira-600 p-1" title="편집">
              <Pencil size={16} />
            </button>
          )}
        </div>
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
        <MarkdownViewer content={content} />
      )}
    </div>
  );
}
