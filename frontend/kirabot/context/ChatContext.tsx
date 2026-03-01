import React, { createContext, useContext, useReducer } from 'react';
import type {
  ChatMessage,
  ContextPanelContent,
  Conversation,
  ConversationPhase,
  OpinionMode,
} from '../types';

// ── State ──

export interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  sidebarCollapsed: boolean;
  contextPanel: ContextPanelContent;
  isProcessing: boolean;
}

const initialState: ChatState = {
  conversations: [],
  activeConversationId: null,
  sidebarCollapsed: false,
  contextPanel: { type: 'none' },
  isProcessing: false,
};

// ── Actions ──

type ChatAction =
  | { type: 'CREATE_CONVERSATION'; conversation: Conversation }
  | { type: 'SET_ACTIVE'; id: string | null }
  | { type: 'DELETE_CONVERSATION'; id: string }
  | { type: 'PUSH_MESSAGE'; conversationId: string; message: ChatMessage }
  | { type: 'UPDATE_MESSAGE'; conversationId: string; messageId: string; updates: Partial<ChatMessage> }
  | { type: 'REMOVE_LAST_STATUS'; conversationId: string }
  | { type: 'SET_PHASE'; conversationId: string; phase: ConversationPhase }
  | { type: 'SET_CONTEXT_PANEL'; content: ContextPanelContent }
  | { type: 'SET_PROCESSING'; value: boolean }
  | { type: 'SET_SIDEBAR_COLLAPSED'; value: boolean }
  | { type: 'UPDATE_CONVERSATION'; conversationId: string; updates: Partial<Conversation> }
  | { type: 'LOAD_CONVERSATIONS'; conversations: Conversation[]; activeId: string | null };

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'CREATE_CONVERSATION':
      return {
        ...state,
        conversations: [action.conversation, ...state.conversations],
        activeConversationId: action.conversation.id,
        contextPanel: { type: 'none' },
      };

    case 'SET_ACTIVE':
      return { ...state, activeConversationId: action.id, contextPanel: { type: 'none' } };

    case 'DELETE_CONVERSATION': {
      const filtered = state.conversations.filter((c) => c.id !== action.id);
      const newActiveId =
        state.activeConversationId === action.id
          ? filtered[0]?.id ?? null
          : state.activeConversationId;
      return { ...state, conversations: filtered, activeConversationId: newActiveId };
    }

    case 'PUSH_MESSAGE':
      return {
        ...state,
        conversations: state.conversations.map((c) =>
          c.id === action.conversationId
            ? { ...c, messages: [...c.messages, action.message] }
            : c,
        ),
      };

    case 'UPDATE_MESSAGE':
      return {
        ...state,
        conversations: state.conversations.map((c) =>
          c.id === action.conversationId
            ? {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === action.messageId ? { ...m, ...action.updates } as ChatMessage : m,
                ),
              }
            : c,
        ),
      };

    case 'REMOVE_LAST_STATUS':
      return {
        ...state,
        conversations: state.conversations.map((c) => {
          if (c.id !== action.conversationId) return c;
          const msgs = c.messages;
          let lastStatusIdx = -1;
          for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].type === 'status') { lastStatusIdx = i; break; }
          }
          if (lastStatusIdx >= 0) {
            return { ...c, messages: [...msgs.slice(0, lastStatusIdx), ...msgs.slice(lastStatusIdx + 1)] };
          }
          return c;
        }),
      };

    case 'SET_PHASE':
      return {
        ...state,
        conversations: state.conversations.map((c) =>
          c.id === action.conversationId ? { ...c, phase: action.phase } : c,
        ),
      };

    case 'SET_CONTEXT_PANEL':
      return { ...state, contextPanel: action.content };

    case 'SET_PROCESSING':
      return { ...state, isProcessing: action.value };

    case 'SET_SIDEBAR_COLLAPSED':
      return { ...state, sidebarCollapsed: action.value };

    case 'UPDATE_CONVERSATION':
      return {
        ...state,
        conversations: state.conversations.map((c) =>
          c.id === action.conversationId ? { ...c, ...action.updates } : c,
        ),
      };

    case 'LOAD_CONVERSATIONS':
      return {
        ...state,
        conversations: action.conversations,
        activeConversationId: action.activeId,
      };

    default:
      return state;
  }
}

// ── Context ──

interface ChatContextValue {
  state: ChatState;
  dispatch: React.Dispatch<ChatAction>;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);

  return (
    <ChatContext.Provider value={{ state, dispatch }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider');
  return ctx;
}

// ── Helper: create new conversation ──

let conversationCounter = 0;

export function createNewConversation(opinionMode: OpinionMode = 'balanced'): Conversation {
  conversationCounter += 1;
  const now = Date.now();
  return {
    id: `conv_${now}_${conversationCounter}`,
    title: 'Kira',
    messages: [],
    createdAt: now,
    phase: 'greeting',
    opinionMode,
  };
}
