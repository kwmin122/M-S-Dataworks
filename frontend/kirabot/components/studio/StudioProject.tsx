import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import StudioLayout from './StudioLayout';
import RfpStage from './stages/RfpStage';
import PackageStage from './stages/PackageStage';
import CompanyStage from './stages/CompanyStage';
import StyleStage from './stages/StyleStage';
import GenerateStage from './stages/GenerateStage';
import ChecklistStage from './stages/ChecklistStage';
import ReviewStage from './stages/ReviewStage';
import ErrorToast, { makeToastId, type ToastMessage } from './ErrorToast';
import {
  getStudioProject,
  updateStudioStage,
  analyzeRfpText,
  classifyPackage,
  STUDIO_STAGES,
  type StudioProject as StudioProjectType,
  type StudioStage,
  type ClassifyResult,
} from '../../services/studioApi';

const VALID_STAGES = new Set<string>(STUDIO_STAGES.map(s => s.key));

export default function StudioProject() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<StudioProjectType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [classifyResult, setClassifyResult] = useState<ClassifyResult | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((text: string) => {
    setToasts((prev) => [...prev, { id: makeToastId(), text }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const loadProject = useCallback(() => {
    if (!projectId) return;
    setLoading(true);
    setError('');
    getStudioProject(projectId)
      .then(setProject)
      .catch((err) => {
        setError(err.message || '프로젝트를 불러올 수 없습니다');
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  const handleStageChange = useCallback(
    async (stage: StudioStage) => {
      if (!projectId || !project) return;
      const previousStage = project.studio_stage;
      try {
        // Optimistically update stage for immediate UI feedback
        setProject((prev) => prev ? { ...prev, studio_stage: stage } : prev);
        const updated = await updateStudioStage(projectId, stage);
        setProject(updated);
      } catch (err: unknown) {
        // Revert to previous stage on failure
        setProject((prev) => prev ? { ...prev, studio_stage: previousStage } : prev);
        const msg = err instanceof Error ? err.message : '단계 변경 실패';
        addToast(msg);
      }
    },
    [projectId, project, addToast],
  );

  const handleAnalyze = useCallback(async (text: string) => {
    if (!projectId) return;
    const result = await analyzeRfpText(projectId, text);
    setProject(result.project);
  }, [projectId]);

  const handleClassify = useCallback(async () => {
    if (!projectId) return;
    const result = await classifyPackage(projectId);
    setClassifyResult(result);
    // Refresh project to get updated stage
    const updated = await getStudioProject(projectId);
    setProject(updated);
  }, [projectId]);

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
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={loadProject}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700 transition-colors"
            >
              <RefreshCw size={14} />
              다시 시도
            </button>
            <button
              onClick={() => navigate('/studio')}
              className="text-sm text-slate-500 hover:text-slate-700"
            >
              목록으로 돌아가기
            </button>
          </div>
        </div>
      </div>
    );
  }

  const rawStage = project.studio_stage ?? 'rfp';
  const currentStage: StudioStage = VALID_STAGES.has(rawStage) ? (rawStage as StudioStage) : 'rfp';

  return (
    <>
      <StudioLayout
        project={project}
        currentStage={currentStage}
        onStageChange={handleStageChange}
      >
        <StageContent
          stage={currentStage}
          project={project}
          onAnalyze={handleAnalyze}
          onClassify={handleClassify}
          classifyResult={classifyResult}
          onProjectUpdate={() => projectId && getStudioProject(projectId).then(setProject)}
        />
      </StudioLayout>
      <ErrorToast messages={toasts} onDismiss={dismissToast} />
    </>
  );
}

function StageContent({
  stage,
  project,
  onAnalyze,
  onClassify,
  classifyResult,
  onProjectUpdate,
}: {
  stage: StudioStage;
  project: StudioProjectType;
  onAnalyze: (text: string) => Promise<void>;
  onClassify: () => Promise<void>;
  classifyResult: ClassifyResult | null;
  onProjectUpdate: () => void;
}) {
  switch (stage) {
    case 'rfp':
      return <RfpStage project={project} onAnalyze={onAnalyze} onClassify={onClassify} onProjectUpdate={onProjectUpdate} />;
    case 'package':
      return (
        <PackageStage
          projectId={project.id}
          procurementDomain={classifyResult?.procurement_domain}
          contractMethod={classifyResult?.contract_method}
          confidence={classifyResult?.confidence}
          reviewRequired={classifyResult?.review_required}
          matchedSignals={classifyResult?.matched_signals}
          classifierWarnings={classifyResult?.warnings}
        />
      );
    case 'company':
      return <CompanyStage projectId={project.id} />;
    case 'style':
      return (
        <StyleStage
          projectId={project.id}
          pinnedStyleSkillId={project.pinned_style_skill_id}
          onProjectUpdate={onProjectUpdate}
        />
      );
    case 'generate':
      return (
        <GenerateStage
          projectId={project.id}
          project={project}
          onProjectUpdate={onProjectUpdate}
        />
      );
    case 'review':
      return (
        <ReviewStage
          projectId={project.id}
          project={project}
          onProjectUpdate={onProjectUpdate}
        />
      );
    case 'relearn':
      return <ChecklistStage projectId={project.id} />;
    default:
      return <StagePlaceholder stage={stage} />;
  }
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
