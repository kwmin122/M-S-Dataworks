import React from 'react';
import { Layers, Plus, PanelLeftClose, PanelLeft } from 'lucide-react';

interface SidebarHeaderProps {
  collapsed: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  onHome?: () => void;
}

const SidebarHeader: React.FC<SidebarHeaderProps> = ({ collapsed, onToggle, onNewChat, onHome }) => {
  return (
    <div className="flex h-14 items-center justify-between border-b border-white/10 px-3">
      {!collapsed && (
        <button
          type="button"
          onClick={onHome}
          className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity"
          title="홈으로 이동"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-700">
            <Layers size={14} className="text-white" />
          </div>
          <span className="text-sm font-bold text-white">M&S Solutions</span>
        </button>
      )}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onNewChat}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
          title="새 대화"
        >
          <Plus size={18} />
        </button>
        <button
          type="button"
          onClick={onToggle}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-sidebar-hover hover:text-white"
          title={collapsed ? '사이드바 펼치기' : '사이드바 접기'}
        >
          {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>
    </div>
  );
};

export default SidebarHeader;
