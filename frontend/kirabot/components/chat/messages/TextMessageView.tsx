import React from 'react';
import { FileText } from 'lucide-react';
import type { TextChatMessage, MessageAction } from '../../../types';

interface Props {
  message: TextChatMessage;
  onAction: (action: MessageAction) => void;
}

/** Simple inline markdown: **bold**, [text](url) */
function renderMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Match **bold** or [text](url)
  const regex = /(\*\*(.+?)\*\*)|(\[([^\]]+)\]\((https?:\/\/[^)]+)\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[1]) {
      // **bold**
      parts.push(<strong key={match.index} className="font-semibold">{match[2]}</strong>);
    } else if (match[3]) {
      // [text](url)
      parts.push(
        <a
          key={match.index}
          href={match[5]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary-600 underline underline-offset-2 hover:text-primary-800"
        >
          {match[4]}
        </a>
      );
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

const TextMessageView: React.FC<Props> = ({ message, onAction }) => {
  return (
    <div>
      <p className="whitespace-pre-line">{renderMarkdown(message.text)}</p>
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
