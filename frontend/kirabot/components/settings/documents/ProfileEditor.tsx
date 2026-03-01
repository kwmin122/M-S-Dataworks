import React, { useEffect, useState, useCallback } from 'react';
import { Settings, RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';
import ProfileSection from './ProfileSection';
import VersionHistory from './VersionHistory';
import { getProfileMd, updateProfileSection, getProfileHistory, rollbackProfile } from '../../../services/kiraApiService';
import type { ProfileSection as ProfileSectionType, ProfileVersion } from '../../../types';

export default function ProfileEditor() {
  const [sections, setSections] = useState<ProfileSectionType[]>([]);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<ProfileVersion[]>([]);
  const [saveMsg, setSaveMsg] = useState('');
  const companyId = 'default';

  const loadProfile = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getProfileMd(companyId);
      setSections(data.sections);
      setVersion(data.metadata.version);
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : '프로필 로드 실패');
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  const handleSave = async (sectionName: string, content: string) => {
    const result = await updateProfileSection(companyId, sectionName, content);
    if (result.success) {
      setVersion(result.version);
      setSaveMsg('저장되었습니다.');
      setTimeout(() => setSaveMsg(''), 3000);
      await loadProfile();
    } else {
      throw new Error('섹션을 찾을 수 없습니다.');
    }
  };

  const handleShowHistory = async () => {
    const data = await getProfileHistory(companyId);
    setHistory(data.versions);
    setShowHistory(true);
  };

  const handleRollback = async (targetVersion: number) => {
    const result = await rollbackProfile(companyId, targetVersion);
    if (result.success) {
      setShowHistory(false);
      setSaveMsg(`v${targetVersion}으로 되돌렸습니다.`);
      setTimeout(() => setSaveMsg(''), 3000);
      await loadProfile();
    }
  };

  if (loading) {
    return <div className="text-center text-slate-400 py-12">프로필 로드 중...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings size={20} className="text-kira-600" />
          <h2 className="text-lg font-semibold text-slate-900">회사 프로필</h2>
          {version > 0 && <span className="text-xs text-slate-400">v{version}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleShowHistory} className="flex items-center gap-1 text-xs text-slate-500 hover:text-kira-600">
            <RefreshCw size={14} /> 버전 이력
          </button>
        </div>
      </div>

      {sections.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
          <p className="text-sm text-slate-500">프로필이 아직 생성되지 않았습니다.</p>
          <p className="text-xs text-slate-400 mt-1">회사 문서를 업로드하면 자동으로 생성됩니다.</p>
        </div>
      ) : (
        sections.map((s) => (
          <ProfileSection
            key={s.name}
            name={s.name}
            content={s.content}
            editable={s.editable}
            onSave={handleSave}
            onShowHistory={s.editable ? handleShowHistory : undefined}
          />
        ))
      )}

      {showHistory && (
        <VersionHistory
          versions={history}
          onRollback={handleRollback}
          onClose={() => setShowHistory(false)}
        />
      )}

      {saveMsg && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl border border-emerald-200 bg-emerald-50 shadow-lg px-5 py-3 text-sm text-emerald-700"
        >
          {saveMsg}
        </motion.div>
      )}
    </div>
  );
}
