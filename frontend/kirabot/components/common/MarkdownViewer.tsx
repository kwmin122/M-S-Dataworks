import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
  content: string;
  className?: string;
}

export default function MarkdownViewer({ content, className }: Props) {
  if (!content) {
    return <p className="text-sm text-slate-400 italic">(비어있음)</p>;
  }

  return (
    <div
      className={[
        'max-w-none text-sm text-slate-600 leading-relaxed',
        '[&_h2]:text-base [&_h2]:font-bold [&_h2]:text-slate-800 [&_h2]:mt-4 [&_h2]:mb-2',
        '[&_h3]:text-sm [&_h3]:font-bold [&_h3]:text-slate-800 [&_h3]:mt-3 [&_h3]:mb-1.5',
        '[&_h4]:text-sm [&_h4]:font-semibold [&_h4]:text-slate-700 [&_h4]:mt-2 [&_h4]:mb-1',
        '[&_p]:my-1.5 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5',
        '[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5',
        '[&_strong]:text-slate-800 [&_a]:text-kira-600 [&_a]:underline',
        '[&_table]:text-xs [&_table]:border-collapse [&_table]:w-full [&_table]:my-2',
        '[&_th]:bg-slate-50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:border [&_th]:border-slate-200',
        '[&_td]:px-2 [&_td]:py-1 [&_td]:border [&_td]:border-slate-200',
        '[&_blockquote]:border-l-4 [&_blockquote]:border-slate-300 [&_blockquote]:pl-3 [&_blockquote]:text-slate-500 [&_blockquote]:italic',
        '[&_hr]:border-slate-200 [&_hr]:my-3',
        '[&_code]:bg-slate-100 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono',
        className ?? '',
      ].join(' ')}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
