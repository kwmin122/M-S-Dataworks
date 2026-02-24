import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useChatContext } from '../../context/ChatContext';
import { usePersistedConversations } from '../../hooks/usePersistedConversations';
import ChatArea from './ChatArea';
import ContextPanel from './ContextPanel';
import type { User } from '../../types';

interface ChatPageProps {
  user: User | null;
}

const ChatPage: React.FC<ChatPageProps> = ({ user }) => {
  usePersistedConversations();

  const { state } = useChatContext();
  const hasPanelContent = state.contextPanel.type !== 'none';

  // Panel ratio (0~1, default 0.5 = 50/50)
  const [panelRatio, setPanelRatio] = useState(0.5);
  const isDragging = useRef(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const sidebarWidth = state.sidebarCollapsed ? 60 : 240;
      const availableWidth = window.innerWidth - sidebarWidth;
      const panelWidth = window.innerWidth - e.clientX;
      const ratio = Math.max(0.25, Math.min(0.65, panelWidth / availableWidth));
      setPanelRatio(ratio);
    };

    const handleMouseUp = () => {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [state.sidebarCollapsed]);

  return (
    <>
      {/* Chat area */}
      <div
        style={hasPanelContent ? { flex: `${1 - panelRatio}` } : undefined}
        className={hasPanelContent ? 'min-w-0 h-full overflow-hidden' : 'flex-1 min-w-0 h-full overflow-hidden'}
      >
        <ChatArea user={user} />
      </div>
      {/* Context panel */}
      {hasPanelContent && (
        <>
          <div
            className="w-1 shrink-0 cursor-col-resize bg-slate-200 hover:bg-primary-300 active:bg-primary-400 transition-colors"
            onMouseDown={handleMouseDown}
          />
          <div style={{ flex: `${panelRatio}` }} className="min-w-0 h-full">
            <ContextPanel />
          </div>
        </>
      )}
    </>
  );
};

export default ChatPage;
