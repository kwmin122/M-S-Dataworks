import React from 'react';
import { Loader2, CheckCircle2, AlertCircle, Info, RotateCcw } from 'lucide-react';
import type { StatusChatMessage, MessageAction } from '../../../types';

interface Props {
  message: StatusChatMessage;
  onAction: (action: MessageAction) => void;
}

const iconMap = {
  loading: <Loader2 size={16} className="animate-spin text-primary-600" />,
  success: <CheckCircle2 size={16} className="text-emerald-600" />,
  error: <AlertCircle size={16} className="text-red-500" />,
  info: <Info size={16} className="text-blue-500" />,
};

const bgMap = {
  loading: 'bg-primary-50 border-primary-200',
  success: 'bg-emerald-50 border-emerald-200',
  error: 'bg-red-50 border-red-200',
  info: 'bg-blue-50 border-blue-200',
};

const StatusMessageView: React.FC<Props> = ({ message, onAction }) => {
  return (
    <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${bgMap[message.level]}`}>
      {message.level === 'loading' ? (
        <div className="flex items-center gap-1.5">
          <div className="flex gap-1">
            <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
            <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
            <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          </div>
          <span className="text-sm text-slate-500">{message.text}</span>
        </div>
      ) : (
        <>
          {iconMap[message.level]}
          <span className="flex-1 text-sm text-slate-700">{message.text}</span>
        </>
      )}
      {message.level === 'error' && message.retryAction && (
        <button
          type="button"
          onClick={() => onAction({ type: 'retry_action', action: message.retryAction! })}
          className="flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
        >
          <RotateCcw size={12} /> 재시도
        </button>
      )}
    </div>
  );
};

export default StatusMessageView;
