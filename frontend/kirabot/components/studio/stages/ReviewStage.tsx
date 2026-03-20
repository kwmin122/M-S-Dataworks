import React, { useState, useEffect, useCallback } from 'react';
import {
  Edit3, Save, GitCompare, Sparkles, Pin, Loader2, AlertCircle,
  CheckCircle2, RefreshCw,
} from 'lucide-react';
import type {
  CurrentRevisionData, RevisionSection, ProposalDiffResult, DiffSection, RelearnResult, StudioProject,
} from '../../../services/studioApi';
import {
  getCurrentRevision, saveEditedProposal, getProposalDiff,
  relearnProposalStyle, pinStyleSkill, generateProposal,
} from '../../../services/studioApi';

interface ReviewStageProps {
  projectId: string;
  project: StudioProject;
  onProjectUpdate: () => void;
}

type ReviewPhase = 'edit' | 'diff' | 'relearn' | 'regenerate';

export default function ReviewStage({ projectId, project, onProjectUpdate }: ReviewStageProps) {
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
      const rev = await getCurrentRevision(projectId, 'proposal');
      setRevision(rev);
      setEditedSections(rev.sections.map(s => ({ ...s })));
    } catch {
      setError('제안서 리비전을 불러올 수 없습니다. 먼저 제안서를 생성해주세요.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadRevision(); }, [loadRevision]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError('');
    try {
      await saveEditedProposal(projectId, editedSections);
      setPhase('diff');
      // Load diff
      const d = await getProposalDiff(projectId);
      setDiff(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  }, [projectId, editedSections]);

  const handleRelearn = useCallback(async () => {
    setActionLoading(true);
    setError('');
    try {
      const result = await relearnProposalStyle(projectId);
      setRelearnResult(result);
      setPhase('relearn');
    } catch (err) {
      setError(err instanceof Error ? err.message : '학습 실패');
    } finally {
      setActionLoading(false);
    }
  }, [projectId]);

  const handlePinAndRegenerate = useCallback(async () => {
    if (!relearnResult) return;
    setActionLoading(true);
    setError('');
    try {
      await pinStyleSkill(projectId, relearnResult.new_skill_id);
      setPhase('regenerate');
      await generateProposal(projectId, { doc_type: 'proposal' });
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
  }, [projectId, relearnResult, onProjectUpdate, loadRevision]);

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
            제안서를 수정하고, 수정 패턴을 학습시켜 다음 생성에 반영합니다
          </p>
        </div>
        <button onClick={loadRevision} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
          <RefreshCw size={16} />
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 mb-4">{error}</div>
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
