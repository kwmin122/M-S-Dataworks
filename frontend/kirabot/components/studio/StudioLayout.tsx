import React from 'react';
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
    <div className="flex flex-1 h-full overflow-hidden">
      <StageNav currentStage={currentStage} onStageChange={onStageChange} />
      <main className="flex-1 overflow-y-auto p-6 bg-slate-50">
        {children}
      </main>
      <ProjectContextPanel project={project} />
    </div>
  );
};

export default StudioLayout;
