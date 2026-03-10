import React from 'react';
import { Trash2 } from 'lucide-react';
import type { DocumentHistoryEntry } from '../../hooks/useDocumentHistory';

interface Props<T> {
  entries: DocumentHistoryEntry<T>[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRemove?: (id: string) => void;
}

export default function DocumentHistorySelect<T>({
  entries,
  selectedId,
  onSelect,
  onRemove,
}: Props<T>) {
  if (entries.length <= 1) return null; // No selector needed for 0 or 1 entries

  return (
    <div className="flex items-center gap-2">
      <select
        value={selectedId || ''}
        onChange={e => onSelect(e.target.value)}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:border-kira-500 focus:ring-1 focus:ring-kira-200 outline-none"
      >
        {entries.map(entry => (
          <option key={entry.id} value={entry.id}>
            {entry.label} ({new Date(entry.timestamp).toLocaleDateString('ko-KR')})
          </option>
        ))}
      </select>
      {onRemove && selectedId && entries.length > 1 && (
        <button
          type="button"
          onClick={() => onRemove(selectedId)}
          className="rounded-lg p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
          title="이 항목 삭제"
        >
          <Trash2 size={14} />
        </button>
      )}
    </div>
  );
}
