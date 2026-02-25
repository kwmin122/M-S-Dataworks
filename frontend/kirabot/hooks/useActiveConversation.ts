import { useMemo } from 'react';
import { useChatContext } from '../context/ChatContext';
import type { ChatMessage, Conversation } from '../types';

interface ActiveConversation {
  conversation: Conversation | null;
  messages: ChatMessage[];
  conversationId: string | null;
}

export function useActiveConversation(): ActiveConversation {
  const { state } = useChatContext();

  return useMemo(() => {
    const conversation =
      state.conversations.find((c) => c.id === state.activeConversationId) ?? null;
    return {
      conversation,
      messages: conversation?.messages ?? [],
      conversationId: state.activeConversationId,
    };
  }, [state.conversations, state.activeConversationId]);
}
