import React from 'react';
import { Bot, User as UserIcon } from 'lucide-react';
import type { ChatMessage, MessageAction } from '../../types';
import TextMessageView from './messages/TextMessageView';
import ButtonChoiceView from './messages/ButtonChoiceView';
import BidCardListView from './messages/BidCardListView';
import AnalysisResultView from './messages/AnalysisResultView';
import InlineFormView from './messages/InlineFormView';
import FileUploadView from './messages/FileUploadView';
import StatusMessageView from './messages/StatusMessageView';

interface Props {
  message: ChatMessage;
  onAction: (action: MessageAction) => void;
}

const MessageBubble: React.FC<Props> = ({ message, onAction }) => {
  const isBot = message.role === 'bot';

  const renderContent = () => {
    switch (message.type) {
      case 'text':
        return <TextMessageView message={message} onAction={onAction} />;
      case 'button_choice':
        return <ButtonChoiceView message={message} onAction={onAction} />;
      case 'bid_card_list':
        return <BidCardListView message={message} onAction={onAction} />;
      case 'analysis_result':
        return <AnalysisResultView message={message} onAction={onAction} />;
      case 'inline_form':
        return <InlineFormView message={message} onAction={onAction} />;
      case 'file_upload':
        return <FileUploadView message={message} onAction={onAction} />;
      case 'status':
        return <StatusMessageView message={message} onAction={onAction} />;
      default:
        return null;
    }
  };

  return (
    <div className={`flex ${isBot ? 'justify-start' : 'justify-end'}`}>
      {isBot && (
        <div className="mr-2 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-kira-100 border border-kira-200">
          <Bot className="h-4 w-4 text-kira-600" />
        </div>
      )}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
          isBot
            ? 'bg-gradient-to-br from-kira-50 to-blue-50 border border-kira-100 text-slate-700'
            : 'bg-gradient-to-r from-kira-600 to-kira-700 text-white'
        }`}
      >
        {renderContent()}
      </div>
      {!isBot && (
        <div className="ml-2 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-kira-200 bg-white">
          <UserIcon className="h-4 w-4 text-slate-500" />
        </div>
      )}
    </div>
  );
};

export default MessageBubble;
