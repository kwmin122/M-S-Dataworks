import React, { useState, useEffect, useCallback } from 'react';
import {
  Edit3, Save, GitCompare, Sparkles, Pin, Loader2, AlertCircle,
  CheckCircle2, RefreshCw, ChevronDown, ChevronUp, ShieldCheck,
  AlertTriangle, XCircle, TrendingUp, Lightbulb,
} from 'lucide-react';
import type {
  CurrentRevisionData, RevisionSection, ProposalDiffResult, DiffSection, RelearnResult, StudioProject,
  GenerateDocType, QualityReport, QualityDimension,
} from '../../../services/studioApi';
import {
  getCurrentRevision, saveEditedDocument, getDocumentDiff,
  relearnDocumentStyle, pinStyleSkill, generateProposal,
} from '../../../services/studioApi';

const DOC_TYPE_LABELS: Record<string, string> = {
  proposal: '제안서',
  execution_plan: '수행계획서',
  track_record: '실적기술서',
  presentation: '발표자료',
};

interface ReviewStageProps {
  projectId: string;
  project: StudioProject;
  onProjectUpdate: () => void;
  docType?: GenerateDocType;
}

type ReviewPhase = 'edit' | 'diff' | 'relearn' | 'regenerate';

export default function ReviewStage({ projectId, project, onProjectUpdate, docType = 'proposal' }: ReviewStageProps) {
  const docLabel = DOC_TYPE_LABELS[docType] || '문서';

  const [revision, setRevision] = useState<CurrentRevisionData | null>(null);
  const [editedSections, setEditedSections] = useState<RevisionSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [phase, setPhase] = useState<ReviewPhase>('edit');
  const [saving, setSaving] = useState(false);
  const [diff, setDiff] = useState<ProposalDiffResult | null>(null);
  const [relearnResult, setRelearnResult] = useState<RelearnResult | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadRevision = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const rev = await getCurrentRevision(projectId, docType);
      setRevision(rev);
      setEditedSections(rev.sections.map(s => ({ ...s })));
    } catch {
      setError(`${docLabel} 리비전을 불러올 수 없습니다. 먼저 ${docLabel}를 생성해주세요.`);
    } finally {
      setLoading(false);
    }
  }, [projectId, docType, docLabel]);

  useEffect(() => { loadRevision(); }, [loadRevision]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError('');
    try {
      await saveEditedDocument(projectId, docType, editedSections);
      setPhase('diff');
      // Load diff
      const d = await getDocumentDiff(projectId, docType);
      setDiff(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  }, [projectId, docType, editedSections]);

  const handleRelearn = useCallback(async () => {
    setActionLoading(true);
    setError('');
    try {
      const result = await relearnDocumentStyle(projectId, docType);
      setRelearnResult(result);
      setPhase('relearn');
    } catch (err) {
      setError(err instanceof Error ? err.message : '학습 실패');
    } finally {
      setActionLoading(false);
    }
  }, [projectId, docType]);

  const handlePinAndRegenerate = useCallback(async () => {
    if (!relearnResult) return;
    setActionLoading(true);
    setError('');
    try {
      await pinStyleSkill(projectId, relearnResult.new_skill_id);
      setPhase('regenerate');
      await generateProposal(projectId, { doc_type: docType });
      onProjectUpdate();
      await loadRevision();
      setPhase('edit');
      setDiff(null);
      setRelearnResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '재생성 실패');
      setPhase('relearn'); // recover to relearn phase so user can retry
    } finally {
      setActionLoading(false);
    }
  }, [projectId, docType, relearnResult, onProjectUpdate, loadRevision]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  if (error && !revision) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700 flex items-center gap-2">
        <AlertCircle size={16} />
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">검토/보완</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {docLabel}를 수정하고, 수정 패턴을 학습시켜 다음 생성에 반영합니다
          </p>
        </div>
        <button onClick={loadRevision} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
          <RefreshCw size={16} />
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 mb-4">{error}</div>
      )}

      {/* Quality Gate Report */}
      {revision?.quality_report && (
        <QualityGatePanel report={revision.quality_report} />
      )}

      {/* Phase: Edit */}
      {phase === 'edit' && revision && (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
            <div className="flex items-center gap-2 mb-3">
              <Edit3 size={16} className="text-slate-600" />
              <h3 className="text-sm font-semibold text-slate-700">
                {revision.title || '제안서'} — 리비전 #{revision.revision_number}
              </h3>
            </div>
            <div className="space-y-3">
              {editedSections.map((section, idx) => (
                <div key={idx}>
                  <label className="block text-xs font-medium text-slate-600 mb-1">{section.name}</label>
                  <textarea
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-kira-400"
                    rows={4}
                    value={section.text}
                    onChange={(e) => {
                      const updated = [...editedSections];
                      updated[idx] = { ...updated[idx], text: e.target.value };
                      setEditedSections(updated);
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700 disabled:opacity-50"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            수정 저장 및 비교
          </button>
        </>
      )}

      {/* Phase: Diff */}
      {phase === 'diff' && diff && (
        <>
          <DiffView diff={diff} />
          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={handleRelearn}
              disabled={actionLoading || diff.changed_sections_count === 0}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              수정 패턴 학습
            </button>
            <button
              onClick={() => setPhase('edit')}
              className="px-3 py-2 text-sm text-slate-600 hover:text-slate-800"
            >
              편집으로 돌아가기
            </button>
          </div>
        </>
      )}

      {/* Phase: Relearn result */}
      {phase === 'relearn' && relearnResult && (
        <div className="rounded-xl border border-purple-200 bg-purple-50 p-4 mb-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 size={16} className="text-purple-600" />
            <h3 className="text-sm font-semibold text-purple-800">학습 완료</h3>
          </div>
          <div className="text-sm text-slate-600 space-y-1">
            <p>새 스타일 버전: v{relearnResult.new_skill_version}</p>
            <p>반영된 수정 패턴: {relearnResult.edit_notes_count}건</p>
          </div>
          <button
            onClick={handlePinAndRegenerate}
            disabled={actionLoading}
            className="mt-3 flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700 disabled:opacity-50"
          >
            {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <Pin size={14} />}
            새 스타일 적용 및 재생성
          </button>
        </div>
      )}

      {/* Phase: Regenerate */}
      {phase === 'regenerate' && (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={24} className="animate-spin text-kira-500 mr-2" />
          <span className="text-sm text-slate-500">새 스타일로 재생성 중...</span>
        </div>
      )}
    </div>
  );
}


/* ─── Quality Gate Panel ─── */

const GRADE_STYLES: Record<string, string> = {
  '수': 'text-green-700 bg-green-100 border-green-300',
  '우': 'text-blue-700 bg-blue-100 border-blue-300',
  '미': 'text-yellow-700 bg-yellow-100 border-yellow-300',
  '양': 'text-orange-700 bg-orange-100 border-orange-300',
  '가': 'text-red-700 bg-red-100 border-red-300',
};

function getScoreBarColor(score: number): string {
  if (score >= 0.8) return 'bg-green-500';
  if (score >= 0.5) return 'bg-amber-500';
  return 'bg-red-500';
}

function getOverallBarColor(score: number): string {
  if (score >= 80) return 'bg-green-500';
  if (score >= 50) return 'bg-amber-500';
  return 'bg-red-500';
}

function getStatusBadge(status: string): { label: string; className: string; Icon: typeof CheckCircle2 } {
  switch (status) {
    case 'pass':
      return { label: '통과', className: 'bg-green-50 text-green-700 border-green-200', Icon: CheckCircle2 };
    case 'warn':
      return { label: '주의', className: 'bg-amber-50 text-amber-700 border-amber-200', Icon: AlertTriangle };
    case 'fail':
      return { label: '미달', className: 'bg-red-50 text-red-700 border-red-200', Icon: XCircle };
    default:
      return { label: status, className: 'bg-slate-50 text-slate-700 border-slate-200', Icon: AlertCircle };
  }
}

function QualityGatePanel({ report }: { report: QualityReport }) {
  const [dimensionsExpanded, setDimensionsExpanded] = useState(true);

  const overallScore = report.overall_score ?? 0;
  const grade = report.grade || '-';
  const gradeStyle = GRADE_STYLES[grade] || 'text-slate-700 bg-slate-100 border-slate-300';
  const passCount = report.pass_count ?? 0;
  const warnCount = report.warn_count ?? 0;
  const failCount = report.fail_count ?? 0;
  const totalCount = passCount + warnCount + failCount;

  return (
    <div className="rounded-xl border border-slate-200 bg-white mb-4 overflow-hidden">
      {/* ── Score Summary ── */}
      <div className="p-4 border-b border-slate-100">
        <div className="flex items-center gap-2 mb-3">
          <ShieldCheck size={16} className="text-slate-600" />
          <h3 className="text-sm font-semibold text-slate-700">품질 검증 결과</h3>
        </div>

        <div className="flex items-center gap-4">
          {/* Grade badge */}
          <div className={`flex items-center justify-center w-12 h-12 rounded-xl border-2 text-xl font-extrabold shrink-0 ${gradeStyle}`}>
            {grade}
          </div>

          {/* Score + bar */}
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 mb-1.5">
              <span className="text-2xl font-bold text-slate-900">{overallScore.toFixed(1)}</span>
              <span className="text-sm text-slate-400">/ 100</span>
            </div>
            <div className="w-full h-2.5 rounded-full bg-slate-100 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${getOverallBarColor(overallScore)}`}
                style={{ width: `${Math.min(overallScore, 100)}%` }}
              />
            </div>
          </div>

          {/* Status counts */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex items-center gap-1 text-xs">
              <CheckCircle2 size={13} className="text-green-500" />
              <span className="font-medium text-green-700">{passCount}</span>
            </div>
            <div className="flex items-center gap-1 text-xs">
              <AlertTriangle size={13} className="text-amber-500" />
              <span className="font-medium text-amber-700">{warnCount}</span>
            </div>
            <div className="flex items-center gap-1 text-xs">
              <XCircle size={13} className="text-red-500" />
              <span className="font-medium text-red-700">{failCount}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Dimension Breakdown ── */}
      {report.dimensions && report.dimensions.length > 0 && (
        <div className="border-b border-slate-100">
          <button
            onClick={() => setDimensionsExpanded(!dimensionsExpanded)}
            className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <TrendingUp size={14} className="text-slate-500" />
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                항목별 상세 ({totalCount}개 항목)
              </span>
            </div>
            {dimensionsExpanded
              ? <ChevronUp size={14} className="text-slate-400" />
              : <ChevronDown size={14} className="text-slate-400" />
            }
          </button>

          {dimensionsExpanded && (
            <div className="px-4 pb-4 space-y-2">
              {report.dimensions.map((dim) => (
                <DimensionRow key={dim.name} dimension={dim} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Recommendation ── */}
      {report.recommendation && (
        <div className="px-4 py-3 flex items-start gap-2">
          <Lightbulb size={14} className="text-kira-500 mt-0.5 shrink-0" />
          <p className="text-sm text-slate-600">{report.recommendation}</p>
        </div>
      )}
    </div>
  );
}

function DimensionRow({ dimension }: { dimension: QualityDimension }) {
  const [detailOpen, setDetailOpen] = useState(false);
  const badge = getStatusBadge(dimension.status);
  const scorePercent = Math.round(dimension.score * 100);
  const hasDetails = dimension.details && dimension.details.length > 0;

  return (
    <div className="rounded-lg border border-slate-100 overflow-hidden">
      <button
        onClick={() => hasDetails && setDetailOpen(!detailOpen)}
        className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-slate-50 transition-colors"
        disabled={!hasDetails}
      >
        {/* Status badge */}
        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium border shrink-0 ${badge.className}`}>
          <badge.Icon size={10} />
          {badge.label}
        </span>

        {/* Label */}
        <span className="text-sm font-medium text-slate-700 shrink-0">{dimension.label}</span>

        {/* Score bar */}
        <div className="flex-1 min-w-0">
          <div className="w-full h-1.5 rounded-full bg-slate-100 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${getScoreBarColor(dimension.score)}`}
              style={{ width: `${scorePercent}%` }}
            />
          </div>
        </div>

        {/* Score text */}
        <span className="text-xs font-medium text-slate-500 w-10 text-right shrink-0">{scorePercent}%</span>

        {/* Expand indicator */}
        {hasDetails && (
          detailOpen
            ? <ChevronUp size={12} className="text-slate-300 shrink-0" />
            : <ChevronDown size={12} className="text-slate-300 shrink-0" />
        )}
      </button>

      {/* Detail list */}
      {detailOpen && hasDetails && (
        <div className="px-3 pb-2.5 pt-0">
          <ul className="space-y-1 ml-[72px]">
            {dimension.details.map((detail, i) => (
              <li key={i} className="text-xs text-slate-500 flex items-start gap-1.5">
                <span className="text-slate-300 mt-0.5 shrink-0">-</span>
                <span>{detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}


/* ─── Diff View ─── */

function DiffView({ diff }: { diff: ProposalDiffResult }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 mb-3">
        <GitCompare size={16} className="text-slate-600" />
        <h3 className="text-sm font-semibold text-slate-700">변경 비교</h3>
        <span className="text-xs text-slate-400">
          {diff.changed_sections_count}/{diff.total_sections} 섹션 변경 · 편집률 {Math.round(diff.edit_rate * 100)}%
        </span>
      </div>
      <div className="space-y-3">
        {diff.sections.map((section, idx) => (
          <div key={idx} className={`rounded-lg border p-3 ${section.changed ? 'border-amber-200 bg-amber-50/30' : 'border-slate-100'}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-medium text-slate-700">{section.name}</span>
              {section.changed ? (
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">변경됨</span>
              ) : (
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500">동일</span>
              )}
            </div>
            {section.changed && (
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-400 block mb-1">원본</span>
                  <div className="bg-red-50 rounded p-2 text-slate-600 max-h-24 overflow-y-auto">{section.original.slice(0, 200)}{section.original.length > 200 ? '...' : ''}</div>
                </div>
                <div>
                  <span className="text-slate-400 block mb-1">수정</span>
                  <div className="bg-green-50 rounded p-2 text-slate-600 max-h-24 overflow-y-auto">{section.edited.slice(0, 200)}{section.edited.length > 200 ? '...' : ''}</div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
