import React, { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import MessageBubble from './MessageBubble';
import { slideUp } from '../../utils/animations';
import type { MessageAction } from '../../types';

interface Props {
  onAction: (action: MessageAction) => void;
}

const MessageList: React.FC<Props> = ({ onAction }) => {
  const { messages } = useActiveConversation();
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
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export default MessageList;
