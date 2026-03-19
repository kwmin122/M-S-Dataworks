import React, { useState, useEffect, useCallback } from 'react';
import {
  Palette, Pin, PinOff, ArrowUpCircle, GitBranch, Plus,
  Loader2, AlertCircle, CheckCircle2, FileText,
} from 'lucide-react';
import type { StyleSkill } from '../../../services/studioApi';
import {
  listStyleSkills, createStyleSkill, pinStyleSkill, unpinStyleSkill,
  deriveStyleSkill, promoteStyleSkill,
} from '../../../services/studioApi';

interface StyleStageProps {
  projectId: string;
  pinnedStyleSkillId: string | null;
  onProjectUpdate: () => void;
}

export default function StyleStage({ projectId, pinnedStyleSkillId, onProjectUpdate }: StyleStageProps) {
  const [skills, setSkills] = useState<StyleSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showDeriveForm, setShowDeriveForm] = useState<string | null>(null);

  const loadSkills = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listStyleSkills(projectId);
      setSkills(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '스타일 목록을 불러올 수 없습니다');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadSkills(); }, [loadSkills]);

  const handlePin = useCallback(async (skillId: string) => {
    setActionLoading(skillId);
    try {
      await pinStyleSkill(projectId, skillId);
      onProjectUpdate();
      await loadSkills();
    } catch (err) {
      setError(err instanceof Error ? err.message : '핀 설정 실패');
    } finally {
      setActionLoading(null);
    }
  }, [projectId, loadSkills, onProjectUpdate]);

  const handleUnpin = useCallback(async () => {
    setActionLoading('unpin');
    try {
      await unpinStyleSkill(projectId);
      onProjectUpdate();
      await loadSkills();
    } catch (err) {
      setError(err instanceof Error ? err.message : '핀 해제 실패');
    } finally {
      setActionLoading(null);
    }
  }, [projectId, loadSkills, onProjectUpdate]);

  const handlePromote = useCallback(async (skillId: string) => {
    if (!confirm('이 스타일을 조직 기본 스타일로 승격하시겠습니까?')) return;
    setActionLoading(skillId);
    try {
      await promoteStyleSkill(projectId, skillId);
      await loadSkills();
    } catch (err) {
      setError(err instanceof Error ? err.message : '승격 실패');
    } finally {
      setActionLoading(null);
    }
  }, [projectId, loadSkills]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  if (error && skills.length === 0) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700 flex items-center gap-2">
        <AlertCircle size={16} />
        {error}
        <button onClick={loadSkills} className="ml-2 underline">다시 시도</button>
      </div>
    );
  }

  const projectSkills = skills.filter(s => s.project_id !== null);
  const sharedSkills = skills.filter(s => s.project_id === null);

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">스타일 학습</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            제안서 문체와 구조를 정의하세요
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700"
        >
          <Plus size={14} />
          새 스타일
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 mb-4">{error}</div>
      )}

      {/* Pinned skill indicator */}
      {pinnedStyleSkillId && (
        <div className="rounded-lg bg-kira-50 border border-kira-200 p-3 mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-kira-700">
            <Pin size={14} />
            <span className="font-medium">핀 설정됨:</span>
            <span>{skills.find(s => s.id === pinnedStyleSkillId)?.name ?? pinnedStyleSkillId}</span>
          </div>
          <button
            onClick={handleUnpin}
            disabled={actionLoading === 'unpin'}
            className="flex items-center gap-1 text-xs text-kira-600 hover:text-kira-700 disabled:opacity-50"
          >
            {actionLoading === 'unpin' ? <Loader2 size={12} className="animate-spin" /> : <PinOff size={12} />}
            해제
          </button>
        </div>
      )}

      {/* Create form */}
      {showCreateForm && (
        <CreateStyleForm
          projectId={projectId}
          onSaved={() => { setShowCreateForm(false); loadSkills(); }}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      {/* Project-scoped skills */}
      {projectSkills.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">프로젝트 스타일</h3>
          <div className="space-y-2">
            {projectSkills.map(skill => (
              <SkillCard
                key={skill.id}
                skill={skill}
                isPinned={pinnedStyleSkillId === skill.id}
                onPin={handlePin}
                onPromote={handlePromote}
                onDeriveClick={() => setShowDeriveForm(skill.id)}
                actionLoading={actionLoading}
              />
            ))}
          </div>
        </div>
      )}

      {/* Derive form */}
      {showDeriveForm && (
        <DeriveStyleForm
          projectId={projectId}
          parentSkillId={showDeriveForm}
          parentName={skills.find(s => s.id === showDeriveForm)?.name ?? ''}
          parentProfileMd={skills.find(s => s.id === showDeriveForm)?.profile_md_content ?? ''}
          onSaved={() => { setShowDeriveForm(null); loadSkills(); }}
          onCancel={() => setShowDeriveForm(null)}
        />
      )}

      {/* Shared org defaults */}
      {sharedSkills.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-600 mb-3">조직 공유 스타일</h3>
          <div className="space-y-2">
            {sharedSkills.map(skill => (
              <SkillCard
                key={skill.id}
                skill={skill}
                isPinned={pinnedStyleSkillId === skill.id}
                onPin={handlePin}
                onPromote={handlePromote}
                onDeriveClick={() => setShowDeriveForm(skill.id)}
                actionLoading={actionLoading}
              />
            ))}
          </div>
        </div>
      )}

      {skills.length === 0 && !showCreateForm && (
        <div className="text-center py-16">
          <Palette size={40} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm text-slate-500">등록된 스타일이 없습니다.</p>
          <p className="text-xs text-slate-400 mt-1">새 스타일을 만들어 문체를 정의하세요.</p>
        </div>
      )}
    </div>
  );
}


// --- Sub-components ---

function SkillCard({
  skill,
  isPinned,
  onPin,
  onPromote,
  onDeriveClick,
  actionLoading,
}: {
  skill: StyleSkill;
  isPinned: boolean;
  onPin: (id: string) => void;
  onPromote: (id: string) => void;
  onDeriveClick: () => void;
  actionLoading: string | null;
}) {
  const isLoading = actionLoading === skill.id;

  return (
    <div className={`rounded-xl border p-4 bg-white ${isPinned ? 'border-kira-300 ring-1 ring-kira-200' : 'border-slate-200'}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-800 truncate">{skill.name}</span>
            <span className="text-xs text-slate-400">v{skill.version}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
              skill.source_type === 'uploaded' ? 'bg-blue-50 text-blue-600'
                : skill.source_type === 'derived' ? 'bg-purple-50 text-purple-600'
                : 'bg-green-50 text-green-600'
            }`}>
              {skill.source_type === 'uploaded' ? '업로드' : skill.source_type === 'derived' ? '파생' : '승격됨'}
            </span>
            {skill.is_shared_default && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-700">기본</span>
            )}
            {isPinned && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-kira-50 text-kira-700">핀</span>
            )}
          </div>
          {skill.profile_md_content && (
            <div className="flex items-center gap-1 mt-1 text-xs text-slate-400">
              <FileText size={12} />
              <span>{skill.profile_md_content.slice(0, 60)}{skill.profile_md_content.length > 60 ? '...' : ''}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 ml-2 shrink-0">
          {!isPinned && (
            <button
              onClick={() => onPin(skill.id)}
              disabled={isLoading}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-kira-600 disabled:opacity-50"
              title="핀 설정"
            >
              {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Pin size={14} />}
            </button>
          )}
          {/* Derive: available for both project-scoped and shared skills */}
          <button
            onClick={onDeriveClick}
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-purple-600"
            title="파생"
          >
            <GitBranch size={14} />
          </button>
          {/* Promote: only for project-scoped skills */}
          {skill.project_id !== null && (
            <button
              onClick={() => onPromote(skill.id)}
              disabled={isLoading}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-green-600 disabled:opacity-50"
              title="조직 기본값으로 승격"
            >
              <ArrowUpCircle size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


function CreateStyleForm({
  projectId,
  onSaved,
  onCancel,
}: {
  projectId: string;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState('');
  const [profileMd, setProfileMd] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError('스타일 이름을 입력해주세요'); return; }

    setSaving(true);
    setError('');
    try {
      await createStyleSkill(projectId, {
        name: name.trim(),
        profile_md_content: profileMd.trim() || undefined,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-kira-200 bg-kira-50/30 p-4 mb-4">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">새 스타일 추가</h3>
      <div className="space-y-2">
        <div>
          <label htmlFor="style-name" className="block text-xs font-medium text-slate-600 mb-0.5">스타일 이름</label>
          <input
            id="style-name"
            type="text"
            className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-kira-400"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="예: 과거 제안서 기반 v1"
          />
        </div>
        <div>
          <label htmlFor="style-profile" className="block text-xs font-medium text-slate-600 mb-0.5">문체 프로필 (마크다운)</label>
          <textarea
            id="style-profile"
            className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-kira-400"
            rows={4}
            value={profileMd}
            onChange={(e) => setProfileMd(e.target.value)}
            placeholder="# 문체 프로필&#10;- 경어체 사용&#10;- 기술 용어 중심"
          />
        </div>
      </div>
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
      <div className="flex items-center gap-2 mt-3">
        <button type="submit" disabled={saving} className="px-3 py-1.5 text-sm font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700 disabled:opacity-50">
          {saving ? '저장 중...' : '저장'}
        </button>
        <button type="button" onClick={onCancel} className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700">취소</button>
      </div>
    </form>
  );
}


function DeriveStyleForm({
  projectId,
  parentSkillId,
  parentName,
  parentProfileMd,
  onSaved,
  onCancel,
}: {
  projectId: string;
  parentSkillId: string;
  parentName: string;
  parentProfileMd: string;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(`${parentName} (수정)`);
  const [profileMd, setProfileMd] = useState(parentProfileMd);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError('스타일 이름을 입력해주세요'); return; }

    setSaving(true);
    setError('');
    try {
      await deriveStyleSkill(projectId, parentSkillId, {
        name: name.trim(),
        profile_md_content: profileMd.trim() || undefined,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-purple-200 bg-purple-50/30 p-4 mb-4">
      <h3 className="text-sm font-semibold text-slate-700 mb-1">
        <GitBranch size={14} className="inline mr-1" />
        &quot;{parentName}&quot;에서 파생
      </h3>
      <div className="space-y-2 mt-3">
        <div>
          <label htmlFor="derive-name" className="block text-xs font-medium text-slate-600 mb-0.5">새 스타일 이름</label>
          <input
            id="derive-name"
            type="text"
            className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-purple-400"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="derive-profile" className="block text-xs font-medium text-slate-600 mb-0.5">수정된 문체 프로필 (선택)</label>
          <textarea
            id="derive-profile"
            className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-purple-400"
            rows={3}
            value={profileMd}
            onChange={(e) => setProfileMd(e.target.value)}
            placeholder="비워두면 원본 프로필을 상속합니다"
          />
        </div>
      </div>
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
      <div className="flex items-center gap-2 mt-3">
        <button type="submit" disabled={saving} className="px-3 py-1.5 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50">
          {saving ? '저장 중...' : '파생 생성'}
        </button>
        <button type="button" onClick={onCancel} className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700">취소</button>
      </div>
    </form>
  );
}
