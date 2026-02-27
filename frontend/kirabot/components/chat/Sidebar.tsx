import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { MessageSquare, Bell, TrendingUp, Shield } from 'lucide-react';
import { useChatContext } from '../../context/ChatContext';
import { useConversationFlow } from '../../hooks/useConversationFlow';
import SidebarHeader from './SidebarHeader';
import ConversationList from './ConversationList';
import SidebarFooter from './SidebarFooter';
import type { User } from '../../types';

interface SidebarProps {
  user: User | null;
  onLogout: () => void;
  onHome: () => void;
}

const baseNavItems = [
  { path: '/chat', label: '채팅', icon: MessageSquare },
  { path: '/settings/alerts', label: '알림 설정', icon: Bell },
  { path: '/forecast', label: '발주예측', icon: TrendingUp },
];

const Sidebar: React.FC<SidebarProps> = ({ user, onLogout, onHome }) => {
  const { state, dispatch } = useChatContext();
  const { startNewConversation } = useConversationFlow();
  const navigate = useNavigate();
  const location = useLocation();
  const collapsed = state.sidebarCollapsed;

  const navItems = user?.isAdmin
    ? [...baseNavItems, { path: '/admin', label: '관리자', icon: Shield }]
    : baseNavItems;

  return (
    <div
      className={`flex flex-col bg-sidebar shrink-0 transition-all duration-300 ${
        collapsed ? 'w-[60px]' : 'w-60'
      }`}
    >
      <SidebarHeader
        collapsed={collapsed}
        onToggle={() => dispatch({ type: 'SET_SIDEBAR_COLLAPSED', value: !collapsed })}
        onNewChat={() => {
          startNewConversation();
          if (location.pathname !== '/chat') navigate('/chat');
        }}
        onHome={onHome}
      />
      {/* Navigation */}
      <nav className="px-2 py-2 space-y-0.5 border-b border-white/10">
        {navItems.map((item) => {
          const isActive = location.pathname.startsWith(item.path);
          const Icon = item.icon;
          return (
            <button
              key={item.path}
              type="button"
              onClick={() => navigate(item.path)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-sidebar-active/20 text-white'
                  : 'text-slate-400 hover:bg-sidebar-hover hover:text-white'
              } ${collapsed ? 'justify-center px-0' : ''}`}
              title={collapsed ? item.label : undefined}
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>
      <ConversationList
        conversations={state.conversations}
        activeId={state.activeConversationId}
        collapsed={collapsed}
        onSelect={(id) => {
          dispatch({ type: 'SET_ACTIVE', id });
          if (location.pathname !== '/chat') navigate('/chat');
        }}
        onDelete={(id) => dispatch({ type: 'DELETE_CONVERSATION', id })}
        onRename={(id, newTitle) => dispatch({ type: 'UPDATE_CONVERSATION', conversationId: id, updates: { title: newTitle } })}
      />
      <SidebarFooter user={user} collapsed={collapsed} onLogout={onLogout} onHome={onHome} />
    </div>
  );
};

export default Sidebar;
