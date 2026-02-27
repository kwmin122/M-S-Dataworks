import React from 'react';
import { X, FileText } from 'lucide-react';
import { useChatContext } from '../../context/ChatContext';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import { useConversationFlow } from '../../hooks/useConversationFlow';
import PdfViewer from './context/PdfViewer';
import BidDetailView from './context/BidDetailView';
import ProposalPreview from './context/ProposalPreview';
import DocumentViewer from './context/DocumentViewer';

const ContextPanel: React.FC = () => {
  const { state, dispatch } = useChatContext();
  const { conversation } = useActiveConversation();
  const { handleAction } = useConversationFlow();
  const companyDocuments = conversation?.companyDocuments || [];
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

      {/* Company documents section */}
      {companyDocuments.length > 0 && (
        <div className="shrink-0 border-t border-slate-200 p-3">
          <h3 className="text-xs font-semibold text-slate-500 mb-2">
            회사 문서 ({companyDocuments.length})
          </h3>
          <div className="space-y-1">
            {companyDocuments.map((doc) => (
              <div key={doc.source_file} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 group">
                <FileText size={14} className="text-slate-400" />
                <span className="flex-1 text-sm text-slate-700 truncate">{doc.source_file}</span>
                <span className="text-xs text-slate-400">{doc.chunks}</span>
                <button
                  type="button"
                  onClick={() => handleAction({ type: 'delete_company_doc', sourceFile: doc.source_file })}
                  className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-300 hover:text-red-500 transition-all"
                  title="삭제"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => handleAction({ type: 'header_add_company' })}
            className="mt-2 text-xs text-kira-600 hover:text-kira-700 font-medium"
          >
            + 문서 추가
          </button>
        </div>
      )}
    </div>
  );
};

export default ContextPanel;
