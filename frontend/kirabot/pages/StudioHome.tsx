import React, { useState, useEffect, useCallback, useRef } from 'react';
import { PenTool, Plus, Loader2, FolderOpen, Home, MessageSquare, Star, Clock, Building2, ArrowRight } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import Button from '../components/Button';
import {
  listStudioProjects,
  createStudioProject,
  getCuratedBids,
  type StudioProject,
  type CuratedBid,
  STUDIO_STAGES,
} from '../services/studioApi';

export default function StudioHome() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  // Curated bids state
  const [curatedBids, setCuratedBids] = useState<CuratedBid[]>([]);
  const [curatedLoading, setCuratedLoading] = useState(true);
  const [curatedError, setCuratedError] = useState('');
  const [creatingFromBid, setCreatingFromBid] = useState<string | null>(null);

  useEffect(() => {
    listStudioProjects()
      .then((res) => setProjects(res.projects))
      .catch((err) => setError(err.message || '프로젝트 목록을 불러올 수 없습니다'))
      .finally(() => setLoading(false));

    getCuratedBids()
      .then((res) => setCuratedBids(res.bids.slice(0, 5)))
      .catch((err) => {
        const msg = err instanceof Error ? err.message : '';
        // 404 = no company profile — not an error, just skip
        if (!msg.includes('프로필')) {
          setCuratedError(msg || '맞춤 공고를 불러올 수 없습니다');
        }
      })
      .finally(() => setCuratedLoading(false));
  }, []);

  const inFlight = useRef(false);
  const handleCreate = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
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
      inFlight.current = false;
      setCreating(false);
    }
  }, [navigate]);

  const handleCreateFromBid = useCallback(async (bid: CuratedBid) => {
    if (creatingFromBid) return;
    setCreatingFromBid(bid.id);
    setError('');
    try {
      const project = await createStudioProject({
        title: bid.title.slice(0, 500),
        rfp_source_type: 'nara_search',
        rfp_source_ref: bid.id,
      });
      navigate(`/studio/projects/${project.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '프로젝트 생성 실패';
      setError(msg);
    } finally {
      setCreatingFromBid(null);
    }
  }, [navigate, creatingFromBid]);

  return (
    <div className="flex flex-col flex-1 h-full overflow-hidden">
      {/* Top navigation bar */}
      <header className="flex items-center justify-between h-12 shrink-0 border-b border-slate-200 bg-white px-4">
        <Link
          to="/"
          className="flex items-center gap-1.5 text-sm font-bold text-slate-800 hover:text-kira-600 transition-colors"
        >
          <Home size={16} />
          <span>Kira Bot</span>
        </Link>
        <Link
          to="/chat"
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-kira-600 transition-colors"
        >
          <MessageSquare size={15} />
          <span>채팅</span>
        </Link>
      </header>

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

        {/* Curated Bids section */}
        <CuratedBidsSection
          bids={curatedBids}
          loading={curatedLoading}
          error={curatedError}
          creatingFromBid={creatingFromBid}
          onCreateFromBid={handleCreateFromBid}
        />

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
    </div>
  );
}

// --- Curated Bids Section ---

function RelevanceBadge({ score }: { score: number }) {
  let bg: string;
  let text: string;
  if (score >= 80) {
    bg = 'bg-green-50 border-green-200';
    text = 'text-green-700';
  } else if (score >= 60) {
    bg = 'bg-yellow-50 border-yellow-200';
    text = 'text-yellow-700';
  } else {
    bg = 'bg-slate-50 border-slate-200';
    text = 'text-slate-600';
  }
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${bg} ${text}`}>
      {score}점
    </span>
  );
}

function CuratedBidsSection({
  bids,
  loading,
  error,
  creatingFromBid,
  onCreateFromBid,
}: {
  bids: CuratedBid[];
  loading: boolean;
  error: string;
  creatingFromBid: string | null;
  onCreateFromBid: (bid: CuratedBid) => void;
}) {
  // Don't render section if no profile (no bids and no error and not loading)
  if (!loading && !error && bids.length === 0) return null;

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <Star size={16} className="text-amber-500" />
        <h2 className="text-sm font-semibold text-slate-800">맞춤 공고</h2>
        <span className="text-xs text-slate-400">회사 프로필 기반 추천</span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8 rounded-xl border border-slate-100 bg-slate-50/50">
          <Loader2 size={18} className="animate-spin text-slate-400" />
          <span className="ml-2 text-sm text-slate-400">맞춤 공고 분석 중...</span>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3 text-sm text-amber-700">
          {error}
        </div>
      ) : (
        <div className="space-y-2">
          {bids.map((bid) => (
            <CuratedBidCard
              key={bid.id}
              bid={bid}
              isCreating={creatingFromBid === bid.id}
              onCreateProject={() => onCreateFromBid(bid)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CuratedBidCard({
  bid,
  isCreating,
  onCreateProject,
}: {
  bid: CuratedBid;
  isCreating: boolean;
  onCreateProject: () => void;
}) {
  const deadlineLabel = bid.deadlineAt
    ? new Date(bid.deadlineAt).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 hover:border-kira-200 hover:shadow-sm transition-all">
      {/* Score badge */}
      <div className="shrink-0">
        <RelevanceBadge score={bid.relevance_score} />
      </div>

      {/* Bid info */}
      <div className="flex-1 min-w-0">
        <h3 className="text-sm font-medium text-slate-900 truncate" title={bid.title}>
          {bid.title}
        </h3>
        <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
          {bid.issuingOrg && (
            <span className="flex items-center gap-1 truncate">
              <Building2 size={11} className="shrink-0" />
              {bid.issuingOrg}
            </span>
          )}
          {bid.estimatedPrice && (
            <span className="shrink-0">{bid.estimatedPrice}</span>
          )}
          {deadlineLabel && (
            <span className="flex items-center gap-1 shrink-0">
              <Clock size={11} />
              {deadlineLabel}
            </span>
          )}
        </div>
      </div>

      {/* Create project button */}
      <button
        onClick={(e) => { e.stopPropagation(); onCreateProject(); }}
        disabled={isCreating}
        className="shrink-0 flex items-center gap-1 rounded-lg bg-kira-50 px-2.5 py-1.5 text-xs font-medium text-kira-700 hover:bg-kira-100 transition-colors disabled:opacity-50"
        title="이 공고로 프로젝트 생성"
      >
        {isCreating ? (
          <Loader2 size={12} className="animate-spin" />
        ) : (
          <ArrowRight size={12} />
        )}
        <span>프로젝트 생성</span>
      </button>
    </div>
  );
}

// --- Existing components ---

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
