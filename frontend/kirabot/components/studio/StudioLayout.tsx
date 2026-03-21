import React from 'react';
import { Link } from 'react-router-dom';
import { Home, MessageSquare, ChevronLeft } from 'lucide-react';
import StageNav from './StageNav';
import ProjectContextPanel from './ProjectContextPanel';
import type { StudioProject, StudioStage } from '../../services/studioApi';

interface StudioLayoutProps {
  project: StudioProject | null;
  currentStage: StudioStage;
  onStageChange: (stage: StudioStage) => void;
  children: React.ReactNode;
}

const StudioLayout: React.FC<StudioLayoutProps> = ({
  project,
  currentStage,
  onStageChange,
  children,
}) => {
  return (
    <div className="flex flex-col flex-1 h-full overflow-hidden">
      {/* Top navigation bar */}
      <header className="flex items-center justify-between h-12 shrink-0 border-b border-slate-200 bg-white px-4">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="flex items-center gap-1.5 text-sm font-bold text-slate-800 hover:text-kira-600 transition-colors"
          >
            <Home size={16} />
            <span>Kira Bot</span>
          </Link>
          <span className="text-slate-300">|</span>
          <Link
            to="/studio"
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ChevronLeft size={14} />
            <span>프로젝트 목록</span>
          </Link>
        </div>
        <Link
          to="/chat"
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-kira-600 transition-colors"
        >
          <MessageSquare size={15} />
          <span>채팅</span>
        </Link>
      </header>

      {/* Existing layout: StageNav + content + context panel */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <StageNav currentStage={currentStage} onStageChange={onStageChange} />
        <main className="flex-1 overflow-y-auto p-6 bg-slate-50">
          {children}
        </main>
        <ProjectContextPanel project={project} />
      </div>
    </div>
  );
};

export default StudioLayout;
