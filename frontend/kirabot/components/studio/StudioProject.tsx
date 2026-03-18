import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import StudioLayout from './StudioLayout';
import {
  getStudioProject,
  updateStudioStage,
  STUDIO_STAGES,
  type StudioProject as StudioProjectType,
  type StudioStage,
} from '../../services/studioApi';

const VALID_STAGES = new Set<string>(STUDIO_STAGES.map(s => s.key));

export default function StudioProject() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<StudioProjectType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    getStudioProject(projectId)
      .then(setProject)
      .catch((err) => {
        setError(err.message || '프로젝트를 불러올 수 없습니다');
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleStageChange = useCallback(
    async (stage: StudioStage) => {
      if (!projectId) return;
      try {
        const updated = await updateStudioStage(projectId, stage);
        setProject(updated);
        setError('');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '단계 변경 실패';
        setError(msg);
      }
    },
    [projectId],
  );

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-pulse text-slate-400">로딩 중...</div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error || '프로젝트를 찾을 수 없습니다'}</p>
          <button
            onClick={() => navigate('/studio')}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            목록으로 돌아가기
          </button>
        </div>
      </div>
    );
  }

  const rawStage = project.studio_stage ?? 'rfp';
  const currentStage: StudioStage = VALID_STAGES.has(rawStage) ? (rawStage as StudioStage) : 'rfp';

  return (
    <StudioLayout
      project={project}
      currentStage={currentStage}
      onStageChange={handleStageChange}
    >
      <StagePlaceholder stage={currentStage} />
    </StudioLayout>
  );
}

function StagePlaceholder({ stage }: { stage: StudioStage }) {
  const labels: Record<StudioStage, string> = {
    rfp: '공고 분석',
    package: '제출 패키지 분류',
    company: '회사 역량 연결',
    style: '스타일 학습',
    generate: '문서 생성',
    review: '검토/보완',
    relearn: '재학습',
  };

  return (
    <div className="flex items-center justify-center h-64 rounded-xl border-2 border-dashed border-slate-200">
      <div className="text-center">
        <p className="text-lg font-semibold text-slate-700">{labels[stage]}</p>
        <p className="text-sm text-slate-400 mt-1">이 단계의 구현이 진행 중입니다</p>
      </div>
    </div>
  );
}
