import { useEffect, useRef } from 'react';
import { useChatContext } from '../context/ChatContext';
import type { Conversation } from '../types';

const STORAGE_KEY = 'kira_conversations';
const ACTIVE_KEY = 'kira_active_conversation';
const MAX_CONVERSATIONS = 50;
const DEBOUNCE_MS = 500;

export function usePersistedConversations(): void {
  const { state, dispatch } = useChatContext();
  const isLoaded = useRef(false);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const activeId = localStorage.getItem(ACTIVE_KEY);
      if (raw) {
        const conversations: Conversation[] = JSON.parse(raw);
        dispatch({
          type: 'LOAD_CONVERSATIONS',
          conversations,
          activeId: activeId || conversations[0]?.id || null,
        });
      }
    } catch {
      // corrupt data — ignore
    }
    isLoaded.current = true;
  }, [dispatch]);

  // Save to localStorage on change (debounced)
  useEffect(() => {
    if (!isLoaded.current) return;

    const timer = setTimeout(() => {
      try {
        const toSave = state.conversations.slice(0, MAX_CONVERSATIONS);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
        if (state.activeConversationId) {
          localStorage.setItem(ACTIVE_KEY, state.activeConversationId);
        }
      } catch {
        // storage full — ignore
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [state.conversations, state.activeConversationId]);
}
