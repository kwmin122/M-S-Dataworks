import React, { useCallback } from 'react';
import { PanelLeft, PanelRight, PanelRightOpen, FileText, Building2 } from 'lucide-react';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import { useChatContext } from '../../context/ChatContext';
import type { ConversationPhase, DocumentTab, MessageAction } from '../../types';

const HEADER_BUTTON_PHASES = new Set<ConversationPhase>([
  'doc_upload_company',
  'doc_upload_target',
  'doc_analyzing',
  'doc_chat',
  'bid_analyzing',
  'bid_eval_running',
  'bid_eval_results',
]);

interface ChatHeaderProps {
  onAction?: (action: MessageAction) => void;
}

function detectFileType(fileName: string) {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  if (ext === 'pdf') return 'pdf' as const;
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'excel' as const;
  if (['hwp', 'hwpx'].includes(ext)) return 'hwp' as const;
  if (['doc', 'docx'].includes(ext)) return 'docx' as const;
  if (['ppt', 'pptx'].includes(ext)) return 'ppt' as const;
  return 'other' as const;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({ onAction }) => {
  const { conversation } = useActiveConversation();
  const { state, dispatch } = useChatContext();

  const hasContextPanel = state.contextPanel.type !== 'none';
  const showActionButtons =
    conversation?.phase != null && HEADER_BUTTON_PHASES.has(conversation.phase);

  // 문서 URL이 있으면 패널을 다시 열 수 있도록
  const hasDocUrl = Boolean(conversation?.uploadedFileUrl);

  const handleReopenPanel = useCallback(() => {
    if (!conversation?.uploadedFileUrl) return;
    const fileName = conversation.uploadedFileName || 'document.pdf';
    const companyDocs = conversation.companyDocUrls || [];

    const tabs: DocumentTab[] = [];
    tabs.push({
      label: '분석문서',
      url: conversation.uploadedFileUrl,
      fileName,
      fileType: detectFileType(fileName),
      page: 1,
    });
    if (companyDocs.length > 0) {
      tabs.push({
        label: companyDocs.length === 1 ? '회사문서' : `회사문서 (${companyDocs.length})`,
        url: companyDocs[0].url,
        fileName: companyDocs[0].name,
        fileType: detectFileType(companyDocs[0].name),
      });
    }
    dispatch({
      type: 'SET_CONTEXT_PANEL',
      content: { type: 'documents', tabs, activeTabIndex: 0 },
    });
  }, [conversation, dispatch]);

  return (
    <div className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
      <div className="flex items-center gap-2 min-w-0">
        {state.sidebarCollapsed && (
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_SIDEBAR_COLLAPSED', value: false })}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 shrink-0"
            title="사이드바 펼치기"
          >
            <PanelLeft size={18} />
          </button>
        )}
        <h3 className="text-sm font-bold text-slate-800 truncate">
          {conversation?.title || 'Kira'}
        </h3>
        {conversation?.companyProfile?.companyName && (
          <span className="flex items-center gap-1 rounded-full bg-kira-50 border border-kira-200 px-2.5 py-0.5 text-xs text-kira-700 shrink-0">
            <Building2 size={12} />
            {conversation.companyProfile.companyName}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {showActionButtons && (
          <>
            <button
              type="button"
              onClick={() => onAction?.({ type: 'header_upload_target' })}
              className="flex items-center gap-1 rounded-md border border-kira-400 bg-white px-2.5 py-1 text-[13px] font-medium text-kira-600 hover:bg-kira-50 transition-colors"
              disabled={state.isProcessing}
            >
              <FileText size={14} />
              다른 문서 분석
            </button>
            <button
              type="button"
              onClick={() => onAction?.({ type: 'header_add_company' })}
              className="flex items-center gap-1 rounded-md border border-kira-400 bg-white px-2.5 py-1 text-[13px] font-medium text-kira-600 hover:bg-kira-50 transition-colors"
              disabled={state.isProcessing}
            >
              <Building2 size={14} />
              회사 문서 추가
            </button>
          </>
        )}
        {/* 패널 닫힌 상태에서 문서 다시 열기 */}
        {!hasContextPanel && hasDocUrl && (
          <button
            type="button"
            onClick={handleReopenPanel}
            className="flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-[13px] font-medium text-slate-600 hover:bg-slate-50 transition-colors"
            title="문서 패널 열기"
          >
            <PanelRightOpen size={14} />
            문서 보기
          </button>
        )}
        {hasContextPanel && (
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_CONTEXT_PANEL', content: { type: 'none' } })}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            title="패널 닫기"
          >
            <PanelRight size={18} />
          </button>
        )}
      </div>
    </div>
  );
};

export default ChatHeader;
