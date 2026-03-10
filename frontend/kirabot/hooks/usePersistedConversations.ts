import { useEffect, useRef } from 'react';
import { useChatContext } from '../context/ChatContext';
import { useUser } from '../context/UserContext';
import type { Conversation } from '../types';

const LEGACY_KEY = 'kira_conversations';
const LEGACY_ACTIVE_KEY = 'kira_active_conversation';
const MAX_CONVERSATIONS = 50;
const DEBOUNCE_MS = 500;

function storageKey(userId: string) { return `kira_conversations_${userId}`; }
function activeKey(userId: string) { return `kira_active_conversation_${userId}`; }

export function usePersistedConversations(): void {
  const { state, dispatch } = useChatContext();
  const user = useUser();
  const isLoaded = useRef(false);
  const prevUserId = useRef('');
  const userId = user?.id || '';

  // Reset on user change (account switch)
  useEffect(() => {
    if (prevUserId.current && prevUserId.current !== userId) {
      isLoaded.current = false;
      dispatch({ type: 'LOAD_CONVERSATIONS', conversations: [], activeId: null });
    }
    prevUserId.current = userId;
  }, [userId, dispatch]);

  // Load from localStorage on mount (user-scoped)
  useEffect(() => {
    if (!userId) return;

    try {
      const key = storageKey(userId);
      let raw = localStorage.getItem(key);
      let aId = localStorage.getItem(activeKey(userId));

      // Migrate from legacy non-scoped key if user-scoped key doesn't exist
      if (!raw) {
        const legacyRaw = localStorage.getItem(LEGACY_KEY);
        if (legacyRaw) {
          raw = legacyRaw;
          aId = localStorage.getItem(LEGACY_ACTIVE_KEY);
          // Save to user-scoped key and remove legacy
          localStorage.setItem(key, legacyRaw);
          if (aId) localStorage.setItem(activeKey(userId), aId);
          localStorage.removeItem(LEGACY_KEY);
          localStorage.removeItem(LEGACY_ACTIVE_KEY);
        }
      }

      if (raw) {
        const parsed: unknown = JSON.parse(raw);
        if (!Array.isArray(parsed)) {
          // corrupt data — skip
        } else {
          // Validate each conversation has required fields
          const conversations = parsed.filter(
            (c): c is Conversation =>
              c != null &&
              typeof c === 'object' &&
              typeof (c as Record<string, unknown>).id === 'string' &&
              typeof (c as Record<string, unknown>).phase === 'string' &&
              Array.isArray((c as Record<string, unknown>).messages),
          );
          dispatch({
            type: 'LOAD_CONVERSATIONS',
            conversations,
            activeId: aId || conversations[0]?.id || null,
          });
        }
      }
    } catch {
      // corrupt data — ignore
    } finally {
      isLoaded.current = true;
    }
  }, [dispatch, userId]);

  // Save to localStorage on change (debounced)
  useEffect(() => {
    if (!isLoaded.current || !userId) return;

    const timer = setTimeout(() => {
      try {
        const toSave = state.conversations.slice(0, MAX_CONVERSATIONS);
        localStorage.setItem(storageKey(userId), JSON.stringify(toSave));
        if (state.activeConversationId) {
          localStorage.setItem(activeKey(userId), state.activeConversationId);
        }
      } catch {
        // storage full — ignore
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [state.conversations, state.activeConversationId, userId]);
}
