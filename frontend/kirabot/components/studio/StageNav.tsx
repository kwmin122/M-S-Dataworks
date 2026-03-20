import React from 'react';
import { STUDIO_STAGES, type StudioStage } from '../../services/studioApi';

interface StageNavProps {
  currentStage: StudioStage;
  onStageChange: (stage: StudioStage) => void;
}

const StageNav: React.FC<StageNavProps> = ({ currentStage, onStageChange }) => {
  return (
    <nav
      className="flex flex-col gap-1 w-56 shrink-0 border-r border-slate-200 bg-white py-4 px-3 overflow-y-auto"
      aria-label="Studio stages"
    >
      <h2 className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
        워크플로우
      </h2>
      {STUDIO_STAGES.map((stage, idx) => {
        const isActive = stage.key === currentStage;
        return (
          <button
            key={stage.key}
            onClick={() => onStageChange(stage.key)}
            className={`
              flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors text-left
              ${isActive
                ? 'bg-kira-50 text-kira-700'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'}
            `}
            aria-current={isActive ? 'step' : undefined}
            data-testid={`stage-${stage.key}`}
          >
            <span className={`
              flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold
              ${isActive
                ? 'bg-kira-600 text-white'
                : 'bg-slate-200 text-slate-500'}
            `}>
              {idx + 1}
            </span>
            {stage.label}
          </button>
        );
      })}
    </nav>
  );
};

export default StageNav;
