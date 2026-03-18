import React from 'react';
import { Info } from 'lucide-react';
import { STUDIO_STAGES, type StudioProject } from '../../services/studioApi';

interface ProjectContextPanelProps {
  project: StudioProject | null;
}

const ProjectContextPanel: React.FC<ProjectContextPanelProps> = ({ project }) => {
  if (!project) {
    return (
      <aside className="w-72 shrink-0 border-l border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-400">프로젝트를 선택하세요</p>
      </aside>
    );
  }

  const currentStageLabel = STUDIO_STAGES.find(
    (s) => s.key === project.studio_stage
  )?.label ?? project.studio_stage;

  return (
    <aside className="w-72 shrink-0 border-l border-slate-200 bg-white p-4 overflow-y-auto">
      <div className="flex items-center gap-2 mb-4">
        <Info size={16} className="text-slate-400" />
        <h3 className="text-sm font-semibold text-slate-700">프로젝트 정보</h3>
      </div>

      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-slate-400 text-xs">프로젝트명</dt>
          <dd className="text-slate-900 font-medium mt-0.5" data-testid="ctx-title">
            {project.title}
          </dd>
        </div>

        <div>
          <dt className="text-slate-400 text-xs">현재 단계</dt>
          <dd className="mt-0.5">
            <span className="inline-flex items-center rounded-full bg-kira-50 px-2 py-0.5 text-xs font-medium text-kira-700">
              {currentStageLabel}
            </span>
          </dd>
        </div>

        <div>
          <dt className="text-slate-400 text-xs">상태</dt>
          <dd className="text-slate-700 mt-0.5">{project.status}</dd>
        </div>

        {project.active_analysis_snapshot_id && (
          <div>
            <dt className="text-slate-400 text-xs">분석 스냅샷</dt>
            <dd className="text-slate-500 text-xs mt-0.5 font-mono truncate">
              {project.active_analysis_snapshot_id}
            </dd>
          </div>
        )}

        {project.pinned_style_skill_id && (
          <div>
            <dt className="text-slate-400 text-xs">적용 스타일</dt>
            <dd className="text-slate-500 text-xs mt-0.5 font-mono truncate">
              {project.pinned_style_skill_id}
            </dd>
          </div>
        )}
      </dl>
    </aside>
  );
};

export default ProjectContextPanel;
