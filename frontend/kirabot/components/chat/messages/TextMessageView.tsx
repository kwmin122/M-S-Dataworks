import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText } from 'lucide-react';
import type { TextChatMessage, MessageAction } from '../../../types';

interface Props {
  message: TextChatMessage;
  onAction: (action: MessageAction) => void;
}

const TextMessageView: React.FC<Props> = ({ message, onAction }) => {
  return (
    <div>
      <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-headings:my-2 prose-headings:text-base">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
      </div>
      {message.scoped_to && message.scoped_to.length > 0 && (
        <div className="flex items-center gap-1 mt-2 text-xs text-slate-400">
          <FileText size={10} />
          <span>기반 문서: {message.scoped_to.join(', ')}</span>
        </div>
      )}
      {message.references && message.references.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {message.references.slice(0, 5).map((ref, idx) => (
            <button
              key={`${message.id}_ref_${idx}`}
              type="button"
              className="rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100"
              onClick={() => onAction({ type: 'reference_clicked', page: ref.page, text: ref.text })}
              title={ref.text || `p.${ref.page}`}
            >
              p.{ref.page}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default TextMessageView;
