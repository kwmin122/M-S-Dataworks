import React, { useState } from 'react';
import { FileDown } from 'lucide-react';
import Button from '../Button';

interface ProposalSection {
  [key: string]: string;
}

interface ProposalPanelProps {
  organizationId: string;
}

const ProposalPanel: React.FC<ProposalPanelProps> = ({ organizationId }) => {
  const [bidNoticeId, setBidNoticeId] = useState('');
  const [sections, setSections] = useState<ProposalSection | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [editedSections, setEditedSections] = useState<ProposalSection>({});

  const handleGenerate = async () => {
    if (!bidNoticeId.trim()) return;
    setIsLoading(true);
    try {
      const res = await fetch('/api/proposals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ organizationId, bidNoticeId }),
      });
      const data = await res.json() as { sections: ProposalSection };
      setSections(data.sections);
      setEditedSections(data.sections);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = () => {
    if (!editedSections) return;
    const text = Object.entries(editedSections)
      .map(([k, v]) => `## ${k}\n\n${v}`)
      .join('\n\n---\n\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'proposal_draft.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="flex items-center gap-2 p-3 border-b border-slate-200 bg-slate-50">
        <input
          value={bidNoticeId}
          onChange={(e) => setBidNoticeId(e.target.value)}
          placeholder="공고 ID 입력"
          className="flex-1 h-8 rounded-lg border border-slate-300 px-2 text-xs outline-none focus:border-primary-500"
        />
        <Button size="sm" onClick={() => void handleGenerate()} disabled={isLoading || !bidNoticeId}>
          {isLoading ? '생성 중...' : '초안 생성'}
        </Button>
        {sections && (
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
          >
            <FileDown className="h-3 w-3" /> 다운로드
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {!sections ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400 text-center">
            공고 ID를 입력하고 초안 생성을 누르세요.<br/>
            <span className="text-xs mt-1 block">회사 프로필 정보가 자동으로 반영됩니다.</span>
          </div>
        ) : (
          Object.entries(editedSections).map(([key, value]) => (
            <div key={key} className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs font-semibold text-slate-700 mb-1">{key}</p>
              <textarea
                value={value}
                onChange={(e) => setEditedSections((prev) => ({ ...prev, [key]: e.target.value }))}
                className="w-full text-xs text-slate-600 leading-relaxed outline-none resize-none min-h-[60px]"
                rows={3}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ProposalPanel;
