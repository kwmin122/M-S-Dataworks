import React, { useEffect, useState } from 'react';
import { Plus, Lightbulb, X } from 'lucide-react';
import ChatHeader from './ChatHeader';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import WelcomeScreen from './WelcomeScreen';
import CompanyOnboardingModal from './CompanyOnboardingModal';
import PendingKnowledgeModal from './PendingKnowledgeModal';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import { useConversationFlow } from '../../hooks/useConversationFlow';
import { useChatContext } from '../../context/ChatContext';
import * as kiraApi from '../../services/kiraApiService';
import { sanitizeCompanyId } from '../../services/kiraApiService';
import type { MessageAction, User } from '../../types';

interface ChatAreaProps {
  user: User | null;
}

const ChatArea: React.FC<ChatAreaProps> = ({ user }) => {
  const { conversation } = useActiveConversation();
  const { dispatch } = useChatContext();
  const { startNewConversation, handleUserText, handleAction } = useConversationFlow();
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const [isOnboardingModalOpen, setIsOnboardingModalOpen] = useState(false);
  const [isPendingKnowledgeModalOpen, setIsPendingKnowledgeModalOpen] = useState(false);

  const onAction = (action: MessageAction) => {
    if (action.type === 'open_company_onboarding') {
      setIsOnboardingModalOpen(true);
      return;
    }
    if (action.type === 'open_pending_knowledge') {
      setIsPendingKnowledgeModalOpen(true);
      return;
    }
    void handleAction(action);
  };

  const handleOnboardingComplete = (companyName: string) => {
    sessionStorage.setItem('kira_company_id', sanitizeCompanyId(companyName));
    // Update conversation with company name
    if (conversation) {
      dispatch({
        type: 'UPDATE_CONVERSATION',
        conversationId: conversation.id,
        updates: {
          companyProfile: {
            companyName,
            businessType: '',
            businessNumber: '',
            certifications: [],
            regions: [],
            employeeCount: null,
            annualRevenue: '',
            keyExperience: [],
            specializations: [],
            documents: [],
            aiExtraction: null,
            lastAnalyzedAt: null,
            createdAt: new Date().toISOString(),
          },
        },
      });
    }
    setIsOnboardingModalOpen(false);
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

  // Listen for company DB start event (from UserGuide button)
  useEffect(() => {
    const handler = () => {
      onAction({ type: 'welcome_action', value: 'company_onboarding' });
    };
    window.addEventListener('kira:start-company-db', handler);
    return () => window.removeEventListener('kira:start-company-db', handler);
  }, [handleAction]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-trigger onboarding when no company DB data exists
  useEffect(() => {
    if (isOnboardingModalOpen) return;
    if (conversation?.phase !== 'greeting') return;
    const companyId = sessionStorage.getItem('kira_company_id');
    if (companyId) return;
    const dismissed = sessionStorage.getItem('kira_onboarding_dismissed');
    if (dismissed) return;

    let cancelled = false;
    kiraApi.getCompanyDbProfile().then(profile => {
      if (cancelled) return;
      if (profile && (profile.track_record_count > 0 || profile.personnel_count > 0)) {
        sessionStorage.setItem('kira_company_id', sanitizeCompanyId(profile.company_name || '_default'));
        return;
      }
      // No company data — show onboarding after brief delay
      setTimeout(() => {
        if (!cancelled) setIsOnboardingModalOpen(true);
      }, 1500);
    }).catch(() => {});

    return () => { cancelled = true; };
  }, [conversation?.phase, conversation?.id]); // eslint-disable-line react-hooks/exhaustive-deps

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
      <CompanyOnboardingModal
        isOpen={isOnboardingModalOpen}
        onClose={() => setIsOnboardingModalOpen(false)}
        onComplete={handleOnboardingComplete}
        sessionId={conversation?.sessionId || ''}
      />
      <PendingKnowledgeModal
        isOpen={isPendingKnowledgeModalOpen}
        onClose={() => setIsPendingKnowledgeModalOpen(false)}
        companyId={conversation?.sessionId || 'default'}
        docType="proposal"
      />
    </div>
  );
};

export default ChatArea;
