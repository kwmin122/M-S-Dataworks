import React from 'react';
import { CheckSquare, Square, AlertCircle, Clock } from 'lucide-react';
import type { ChecklistChatMessage, MessageAction } from '../../../types';

interface Props {
  message: ChecklistChatMessage;
  onAction?: (action: MessageAction) => void;
}

const ChecklistView: React.FC<Props> = ({ message }) => {
  const { items, total, mandatory_count } = message;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <CheckSquare size={16} className="text-kira-600" />
        <span className="text-sm font-semibold text-slate-800">제출 체크리스트</span>
        <span className="text-xs text-slate-500">
          (총 {total}건, 필수 {mandatory_count}건)
        </span>
      </div>

      <div className="space-y-1.5 max-h-[400px] overflow-y-auto">
        {items.map((item, idx) => (
          <div
            key={idx}
            className="flex items-start gap-2 rounded-lg border border-slate-100 bg-white px-3 py-2"
          >
            {item.is_mandatory ? (
              <AlertCircle size={14} className="mt-0.5 shrink-0 text-red-500" />
            ) : (
              <Square size={14} className="mt-0.5 shrink-0 text-slate-400" />
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-700">{item.document_name}</span>
                {item.is_mandatory && (
                  <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-600">
                    필수
                  </span>
                )}
                {!item.is_mandatory && (
                  <span className="rounded bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                    선택
                  </span>
                )}
              </div>
              {item.format_hint && (
                <p className="mt-0.5 text-[11px] text-slate-500">형식: {item.format_hint}</p>
              )}
              {item.deadline_note && (
                <p className="mt-0.5 flex items-center gap-1 text-[11px] text-amber-600">
                  <Clock size={10} />
                  {item.deadline_note}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ChecklistView;
