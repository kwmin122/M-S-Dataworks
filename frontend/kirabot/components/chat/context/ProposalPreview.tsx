import React, { useState } from 'react';
import { Copy, FileDown } from 'lucide-react';
import type { ProposalSections } from '../../../types';

interface Props {
  sections: ProposalSections;
  bidNoticeId: string;
  onSectionsChange: (sections: ProposalSections) => void;
}

const ProposalPreview: React.FC<Props> = ({ sections, bidNoticeId, onSectionsChange }) => {
  const [copied, setCopied] = useState(false);

  const handleChange = (key: string, value: string) => {
    onSectionsChange({ ...sections, [key]: value });
  };

  const buildMarkdown = () => {
    return Object.entries(sections)
      .map(([k, v]) => `## ${k}\n\n${v}`)
      .join('\n\n---\n\n');
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(buildMarkdown());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = buildMarkdown();
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    const text = buildMarkdown();
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `proposal_${bidNoticeId}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 200);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
        <span className="text-xs text-slate-500">공고: {bidNoticeId}</span>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            <Copy size={12} /> {copied ? '복사됨' : '복사'}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            <FileDown size={12} /> MD
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {Object.entries(sections).map(([key, value]) => (
          <div key={key} className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs font-semibold text-slate-700 mb-1">{key}</p>
            <textarea
              value={value}
              onChange={(e) => handleChange(key, e.target.value)}
              className="w-full text-xs text-slate-600 leading-relaxed outline-none resize-none min-h-[60px]"
              rows={4}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProposalPreview;
