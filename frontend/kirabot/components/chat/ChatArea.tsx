import React, { useEffect, useState } from 'react';
import { Plus, Lightbulb, X } from 'lucide-react';
import ChatHeader from './ChatHeader';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import WelcomeScreen from './WelcomeScreen';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import { useConversationFlow } from '../../hooks/useConversationFlow';
import type { MessageAction, User } from '../../types';

interface ChatAreaProps {
  user: User | null;
}

const ChatArea: React.FC<ChatAreaProps> = ({ user }) => {
  const { conversation } = useActiveConversation();
  const { startNewConversation, handleUserText, handleAction } = useConversationFlow();
  const [bannerDismissed, setBannerDismissed] = useState(false);

  const onAction = (action: MessageAction) => {
    void handleAction(action);
  };

  const showOnboardingBanner =
    !bannerDismissed &&
    conversation &&
    (!conversation.companyChunks || conversation.companyChunks <= 0) &&
    conversation.phase !== 'doc_upload_company' &&
    conversation.phase !== 'greeting';

  // greeting phase → show welcome screen (messages accumulate silently)
  const isWelcomePhase = conversation?.phase === 'greeting';

  // Auto-start first conversation if none exist
  useEffect(() => {
    if (!conversation) {
      // small delay to avoid double-init from strict mode
      const timer = setTimeout(() => startNewConversation(), 50);
      return () => clearTimeout(timer);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!conversation) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-slate-50">
        <p className="mb-4 text-sm text-slate-500">대화를 시작해보세요</p>
        <button
          type="button"
          onClick={startNewConversation}
          className="flex items-center gap-2 rounded-lg bg-primary-700 px-4 py-2 text-sm text-white hover:bg-primary-800"
        >
          <Plus size={16} /> 새 대화
        </button>
      </div>
    );
  }

  if (isWelcomePhase) {
    return (
      <div className="flex h-full flex-col min-w-0 bg-slate-50">
        <ChatHeader onAction={onAction} />
        <WelcomeScreen
          user={user}
          onSendText={(text) => void handleUserText(text)}
          onAction={onAction}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col min-w-0 bg-slate-50">
      <ChatHeader onAction={onAction} />
      {showOnboardingBanner && (
        <div className="mx-4 mt-3 flex items-center gap-3 rounded-lg border border-primary-200 bg-primary-50 px-4 py-3">
          <Lightbulb size={18} className="shrink-0 text-primary-600" />
          <p className="flex-1 text-sm text-primary-800">
            회사 소개서를 등록하면 GO/NO-GO 판정과 맞춤 분석을 받을 수 있어요
          </p>
          <button
            type="button"
            onClick={() => onAction({ type: 'header_add_company' })}
            className="shrink-0 rounded-md bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700 transition-colors"
          >
            회사 문서 등록하기
          </button>
          <button
            type="button"
            onClick={() => setBannerDismissed(true)}
            className="shrink-0 rounded p-1 text-primary-400 hover:text-primary-600 hover:bg-primary-100 transition-colors"
            aria-label="닫기"
          >
            <X size={16} />
          </button>
        </div>
      )}
      <MessageList onAction={onAction} />
      <ChatInput onSendText={(text, sourceFiles) => void handleUserText(text, sourceFiles)} onAction={onAction} />
    </div>
  );
};

export default ChatArea;
