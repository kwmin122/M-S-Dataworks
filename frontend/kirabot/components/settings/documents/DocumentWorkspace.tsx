import React from 'react';
import { useSearchParams } from 'react-router-dom';
import DocumentTabNav, { type DocumentTab } from './DocumentTabNav';
import ProfileEditor from './ProfileEditor';
import ProposalEditor from './ProposalEditor';
import RfpViewer from './RfpViewer';
import WbsViewer from './WbsViewer';
import PptViewer from './PptViewer';
import TrackRecordViewer from './TrackRecordViewer';

const VALID_TABS: Set<string> = new Set(['profile', 'rfp', 'proposal', 'wbs', 'ppt', 'track_record']);

export default function DocumentWorkspace() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab') || 'profile';
  const activeTab: DocumentTab = VALID_TABS.has(rawTab) ? (rawTab as DocumentTab) : 'profile';

  const handleTabChange = (tab: DocumentTab) => {
    setSearchParams({ tab }, { replace: true });
  };

  return (
    <div className="flex flex-1 min-h-0">
      <DocumentTabNav activeTab={activeTab} onTabChange={handleTabChange} />
      <div className="flex-1 overflow-y-auto p-6 lg:p-8">
        <div className="max-w-4xl mx-auto">
          {activeTab === 'profile' && <ProfileEditor />}
          {activeTab === 'rfp' && <RfpViewer />}
          {activeTab === 'proposal' && <ProposalEditor />}
          {activeTab === 'wbs' && <WbsViewer />}
          {activeTab === 'ppt' && <PptViewer />}
          {activeTab === 'track_record' && <TrackRecordViewer />}
        </div>
      </div>
    </div>
  );
}
