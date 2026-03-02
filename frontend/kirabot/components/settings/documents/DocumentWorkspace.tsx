import React from 'react';
import { useSearchParams } from 'react-router-dom';
import DocumentTabNav, { type DocumentTab } from './DocumentTabNav';
import ProfileEditor from './ProfileEditor';
import ProposalEditor from './ProposalEditor';

const VALID_TABS: Set<string> = new Set(['profile', 'rfp', 'proposal', 'wbs', 'ppt']);

export default function DocumentWorkspace() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab') || 'profile';
  const activeTab: DocumentTab = VALID_TABS.has(rawTab) ? (rawTab as DocumentTab) : 'profile';

  const handleTabChange = (tab: DocumentTab) => {
    setSearchParams({ tab });
  };

  return (
    <div className="flex flex-1 min-h-0">
      <DocumentTabNav activeTab={activeTab} onTabChange={handleTabChange} />
      <div className="flex-1 overflow-y-auto p-6 lg:p-8">
        <div className="max-w-4xl mx-auto">
          {activeTab === 'profile' && <ProfileEditor />}
          {activeTab === 'rfp' && <PlaceholderTab name="RFP 분석결과" />}
          {activeTab === 'proposal' && <ProposalEditor />}
          {activeTab === 'wbs' && <PlaceholderTab name="WBS" />}
          {activeTab === 'ppt' && <PlaceholderTab name="PPT" />}
        </div>
      </div>
    </div>
  );
}

function PlaceholderTab({ name }: { name: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-400">
      {name} 편집 (준비 중)
    </div>
  );
}
