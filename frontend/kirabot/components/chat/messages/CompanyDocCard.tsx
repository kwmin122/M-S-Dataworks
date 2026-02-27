import React, { useState, useEffect, useCallback } from 'react';
import { FileText, X, Undo2, Plus, MessageCircle } from 'lucide-react';
import type { CompanyDocInfo } from '../../../types';

interface CompanyDocCardProps {
  documents: CompanyDocInfo[];
  onDelete: (sourceFile: string) => void;
  onAddMore?: () => void;
  onAskAbout?: (sourceFile: string) => void;
  /** 방금 업로드한 파일명들 (Undo 대상) */
  justUploaded?: string[];
  onUndo?: () => void;
}

const CompanyDocCard: React.FC<CompanyDocCardProps> = ({
  documents,
  onDelete,
  onAddMore,
  onAskAbout,
  justUploaded,
  onUndo,
}) => {
  const [undoVisible, setUndoVisible] = useState(!!justUploaded?.length);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Undo 5초 타이머
  useEffect(() => {
    if (!justUploaded?.length) return;
    setUndoVisible(true);
    const timer = setTimeout(() => setUndoVisible(false), 5000);
    return () => clearTimeout(timer);
  }, [justUploaded]);

  const handleDelete = useCallback((sf: string) => {
    if (confirmDelete === sf) {
      onDelete(sf);
      setConfirmDelete(null);
    } else {
      setConfirmDelete(sf);
      setTimeout(() => setConfirmDelete(null), 3000);
    }
  }, [confirmDelete, onDelete]);

  if (!documents.length) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-2 max-w-sm">
      <p className="text-xs font-medium text-slate-500 mb-1">
        등록된 회사 문서 ({documents.length})
      </p>
      {documents.map((doc) => {
        const isJustUploaded = justUploaded?.includes(doc.source_file);
        return (
          <div
            key={doc.source_file}
            className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm transition-colors ${
              isJustUploaded ? 'bg-kira-50 border border-kira-200' : 'bg-slate-50'
            }`}
          >
            <FileText size={14} className="text-slate-400 flex-shrink-0" />
            <span className="flex-1 truncate text-slate-700">{doc.source_file}</span>
            <span className="text-xs text-slate-400 flex-shrink-0">{doc.chunks}</span>
            {onAskAbout && (
              <button
                type="button"
                onClick={() => onAskAbout(doc.source_file)}
                className="p-0.5 rounded text-slate-300 hover:text-kira-500 transition-colors"
                title="이 문서에 질문"
              >
                <MessageCircle size={14} />
              </button>
            )}
            <button
              type="button"
              onClick={() => handleDelete(doc.source_file)}
              className={`p-0.5 rounded transition-colors ${
                confirmDelete === doc.source_file
                  ? 'text-red-600 bg-red-50'
                  : 'text-slate-300 hover:text-red-500'
              }`}
              title={confirmDelete === doc.source_file ? '다시 클릭하면 삭제' : '삭제'}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}

      <div className="flex items-center gap-2 pt-1">
        {undoVisible && onUndo && (
          <button
            type="button"
            onClick={() => { onUndo(); setUndoVisible(false); }}
            className="flex items-center gap-1 rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100 transition-colors"
          >
            <Undo2 size={12} /> 취소
          </button>
        )}
        {onAddMore && (
          <button
            type="button"
            onClick={onAddMore}
            className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <Plus size={12} /> 문서 추가
          </button>
        )}
      </div>
    </div>
  );
};

export default CompanyDocCard;
