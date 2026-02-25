import React from 'react';
import { X } from 'lucide-react';
import { useChatContext } from '../../context/ChatContext';
import PdfViewer from './context/PdfViewer';
import BidDetailView from './context/BidDetailView';
import ProposalPreview from './context/ProposalPreview';
import DocumentViewer from './context/DocumentViewer';

const ContextPanel: React.FC = () => {
  const { state, dispatch } = useChatContext();
  const content = state.contextPanel;

  if (content.type === 'none') return null;

  const handleClose = () => dispatch({ type: 'SET_CONTEXT_PANEL', content: { type: 'none' } });

  const handleTabChange = (index: number) => {
    if (content.type !== 'documents') return;
    dispatch({
      type: 'SET_CONTEXT_PANEL',
      content: { ...content, activeTabIndex: index },
    });
  };

  const title =
    content.type === 'pdf' ? '문서 미리보기' :
    content.type === 'documents' ? '문서 보기' :
    content.type === 'bid_detail' ? '공고 상세' :
    content.type === 'proposal' ? '제안서 미리보기' : '';

  return (
    <div className="flex h-full w-full flex-col border-l border-slate-200 bg-white">
      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 px-4">
        <span className="text-sm font-semibold text-slate-700">{title}</span>
        <button
          type="button"
          onClick={handleClose}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <X size={18} />
        </button>
      </div>

      {/* Tab bar for documents type */}
      {content.type === 'documents' && content.tabs.length > 1 && (
        <div className="flex shrink-0 border-b border-slate-200 bg-slate-50">
          {content.tabs.map((tab, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handleTabChange(i)}
              className={`flex-1 px-3 py-2.5 text-xs font-medium transition-colors ${
                i === content.activeTabIndex
                  ? 'border-b-2 border-primary-500 text-primary-700 bg-white'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {content.type === 'pdf' && (
          <PdfViewer blobUrl={content.blobUrl} page={content.page} highlightText={content.highlightText} />
        )}
        {content.type === 'documents' && (() => {
          const activeTab = content.tabs[content.activeTabIndex];
          if (!activeTab) return null;
          return (
            <DocumentViewer
              url={activeTab.url}
              fileName={activeTab.fileName}
              fileType={activeTab.fileType}
              page={activeTab.page}
              highlightText={activeTab.highlightText}
            />
          );
        })()}
        {content.type === 'bid_detail' && (
          <BidDetailView bid={content.bid} />
        )}
        {content.type === 'proposal' && (
          <ProposalPreview
            sections={content.sections}
            bidNoticeId={content.bidNoticeId}
            onSectionsChange={(sections) =>
              dispatch({
                type: 'SET_CONTEXT_PANEL',
                content: { type: 'proposal', sections, bidNoticeId: content.bidNoticeId },
              })
            }
          />
        )}
      </div>
    </div>
  );
};

export default ContextPanel;
