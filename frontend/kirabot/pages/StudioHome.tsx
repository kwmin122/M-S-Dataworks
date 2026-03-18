import React, { useState, useEffect, useCallback } from 'react';
import { PenTool, Plus, Loader2, FolderOpen } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/Button';
import {
  listStudioProjects,
  createStudioProject,
  type StudioProject,
  STUDIO_STAGES,
} from '../services/studioApi';

export default function StudioHome() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    listStudioProjects()
      .then(setProjects)
      .catch((err) => setError(err.message || '프로젝트 목록을 불러올 수 없습니다'))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = useCallback(async () => {
    setCreating(true);
    setError('');
    try {
      const project = await createStudioProject({
        title: `새 입찰 프로젝트 ${new Date().toLocaleDateString('ko-KR')}`,
      });
      navigate(`/studio/projects/${project.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '프로젝트 생성 실패';
      setError(msg);
    } finally {
      setCreating(false);
    }
  }, [navigate]);

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-kira-50">
              <PenTool size={20} className="text-kira-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">입찰 문서 AI 작성</h1>
              <p className="text-sm text-slate-500">공고 분석부터 제출 패키지 완성까지</p>
            </div>
          </div>
          <Button onClick={handleCreate} size="sm" disabled={creating}>
            {creating ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Plus size={16} />
            )}
            <span className="ml-1.5">새 프로젝트</span>
          </Button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Project list */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={24} className="animate-spin text-slate-400" />
          </div>
        ) : projects.length === 0 ? (
          <EmptyState onCreateClick={handleCreate} creating={creating} />
        ) : (
          <div className="space-y-3">
            {projects.map((p) => (
              <ProjectCard
                key={p.id}
                project={p}
                onClick={() => navigate(`/studio/projects/${p.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({
  onCreateClick,
  creating,
}: {
  onCreateClick: () => void;
  creating: boolean;
}) {
  return (
    <div className="text-center py-20">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
        <FolderOpen size={28} className="text-slate-400" />
      </div>
      <h2 className="text-lg font-semibold text-slate-700">아직 프로젝트가 없습니다</h2>
      <p className="mt-2 text-sm text-slate-500 leading-relaxed max-w-sm mx-auto">
        새 프로젝트를 만들어 공고를 분석하고<br />
        입찰 제출 패키지를 자동 구성하세요.
      </p>
      <Button onClick={onCreateClick} size="sm" className="mt-6" disabled={creating}>
        {creating ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Plus size={16} />
        )}
        <span className="ml-1.5">첫 프로젝트 만들기</span>
      </Button>
    </div>
  );
}

function ProjectCard({
  project,
  onClick,
}: {
  project: StudioProject;
  onClick: () => void;
}) {
  const stageLabel = STUDIO_STAGES.find(
    (s) => s.key === project.studio_stage,
  )?.label ?? project.studio_stage;

  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl border border-slate-200 bg-white p-4 hover:border-kira-300 hover:shadow-sm transition-all"
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{project.title}</h3>
          <p className="text-xs text-slate-500 mt-1">
            {new Date(project.created_at).toLocaleDateString('ko-KR')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {stageLabel && (
            <span className="inline-flex items-center rounded-full bg-kira-50 px-2.5 py-0.5 text-xs font-medium text-kira-700">
              {stageLabel}
            </span>
          )}
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">
            {project.status}
          </span>
        </div>
      </div>
    </button>
  );
}
