import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { MessageSquare, Bell, TrendingUp, Shield, BookOpen, CirclePlay } from 'lucide-react';
import { useChatContext } from '../../context/ChatContext';
import { useConversationFlow } from '../../hooks/useConversationFlow';
import { startProductTour } from '../onboarding/ProductTour';
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
  { path: '/alerts', label: '알림', icon: Bell },
  { path: '/forecast', label: '발주예측', icon: TrendingUp },
];

const Sidebar: React.FC<SidebarProps> = ({ user, onLogout, onHome }) => {
  const { state, dispatch } = useChatContext();
  const { startNewConversation } = useConversationFlow();
  const navigate = useNavigate();
  const location = useLocation();
  const collapsed = state.sidebarCollapsed;

  const isAdmin = !!user?.isAdmin;

  return (
    <div
      data-tour="sidebar"
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
        {baseNavItems.map((item) => {
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
        {/* Admin link — visually separated */}
        {isAdmin && (
          <>
            <div className="my-1 border-t border-white/10" />
            <button
              type="button"
              onClick={() => navigate('/admin')}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                location.pathname.startsWith('/admin')
                  ? 'bg-sidebar-active/20 text-white'
                  : 'text-slate-400 hover:bg-sidebar-hover hover:text-white'
              } ${collapsed ? 'justify-center px-0' : ''}`}
              title={collapsed ? '관리자' : undefined}
            >
              <Shield size={18} className="shrink-0" />
              {!collapsed && <span>관리자</span>}
            </button>
          </>
        )}
      </nav>
      {/* User Guide + Tour restart (Chat screen only) */}
      {location.pathname === '/chat' && (
        <div className="px-2 py-2 border-b border-white/10 space-y-0.5">
          <button
            data-tour="user-guide"
            type="button"
            onClick={() => dispatch({ type: 'SET_CURRENT_VIEW', view: state.currentView === 'guide' ? 'chat' : 'guide' })}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              state.currentView === 'guide'
                ? 'bg-sidebar-active/20 text-white'
                : 'text-slate-400 hover:bg-sidebar-hover hover:text-white'
            } ${collapsed ? 'justify-center px-0' : ''}`}
            title={collapsed ? '사용 가이드' : undefined}
          >
            <BookOpen size={18} className="shrink-0" />
            {!collapsed && <span>사용 가이드</span>}
          </button>
          <button
            type="button"
            onClick={startProductTour}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-400 hover:bg-sidebar-hover hover:text-white transition-colors ${
              collapsed ? 'justify-center px-0' : ''
            }`}
            title={collapsed ? '투어 다시 보기' : undefined}
          >
            <CirclePlay size={18} className="shrink-0" />
            {!collapsed && <span>투어 다시 보기</span>}
          </button>
        </div>
      )}
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
