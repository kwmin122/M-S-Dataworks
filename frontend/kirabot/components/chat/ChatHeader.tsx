import React from 'react';
import { Bot, PanelRight, FileText, Building2 } from 'lucide-react';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import { useChatContext } from '../../context/ChatContext';
import type { ConversationPhase, MessageAction } from '../../types';

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

const ChatHeader: React.FC<ChatHeaderProps> = ({ onAction }) => {
  const { conversation } = useActiveConversation();
  const { state, dispatch } = useChatContext();

  const hasContextPanel = state.contextPanel.type !== 'none';
  const showActionButtons =
    conversation?.phase != null && HEADER_BUTTON_PHASES.has(conversation.phase);

  return (
    <div className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
      <div className="flex items-center gap-2 min-w-0">
        <Bot className="h-5 w-5 text-kira-600 shrink-0" />
        <h3 className="text-sm font-bold text-slate-800 truncate">
          {conversation?.title || 'Kira Bot'}
        </h3>
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
