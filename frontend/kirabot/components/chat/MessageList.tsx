import React, { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import { useChatContext } from '../../context/ChatContext';
import MessageBubble from './MessageBubble';
import { slideUp } from '../../utils/animations';
import type { MessageAction } from '../../types';

interface Props {
  onAction: (action: MessageAction) => void;
}

const MessageList: React.FC<Props> = ({ onAction }) => {
  const { messages } = useActiveConversation();
  const { state } = useChatContext();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-3xl space-y-4">
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            variants={slideUp}
            initial="hidden"
            animate="visible"
          >
            <MessageBubble message={msg} onAction={onAction} />
          </motion.div>
        ))}
        {state.isProcessing && (
          <div className="flex justify-start">
            <div className="mr-2 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white">
              <div className="flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary-600 [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary-600 [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary-600 [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export default MessageList;
