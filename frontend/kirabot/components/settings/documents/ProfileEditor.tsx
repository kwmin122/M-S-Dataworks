import React, { useEffect, useState, useCallback, useRef } from 'react';
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
  const [saveMsgType, setSaveMsgType] = useState<'success' | 'error'>('success');
  const mountedRef = useRef(true);
  const companyId = 'default';

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const showToast = useCallback((msg: string, type: 'success' | 'error' = 'success') => {
    setSaveMsg(msg);
    setSaveMsgType(type);
    setTimeout(() => { if (mountedRef.current) setSaveMsg(''); }, 3000);
  }, []);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getProfileMd(companyId);
      if (!mountedRef.current) return;
      setSections(data.sections);
      setVersion(data.metadata.version);
    } catch (e) {
      if (!mountedRef.current) return;
      showToast(e instanceof Error ? e.message : '프로필 로드 실패', 'error');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [companyId, showToast]);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  const handleSave = async (sectionName: string, content: string) => {
    try {
      const result = await updateProfileSection(companyId, sectionName, content);
      if (result.success) {
        setVersion(result.version);
        showToast('저장되었습니다.');
        await loadProfile();
      } else {
        showToast('섹션을 찾을 수 없습니다.', 'error');
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : '저장 실패', 'error');
      throw e; // ProfileSection의 finally block이 saving=false로 리셋하도록
    }
  };

  const handleShowHistory = async () => {
    try {
      const data = await getProfileHistory(companyId);
      setHistory(data.versions);
      setShowHistory(true);
    } catch (e) {
      showToast(e instanceof Error ? e.message : '이력 조회 실패', 'error');
    }
  };

  const handleRollback = async (targetVersion: number) => {
    try {
      const result = await rollbackProfile(companyId, targetVersion);
      if (result.success) {
        setShowHistory(false);
        showToast(`v${targetVersion}으로 되돌렸습니다.`);
        await loadProfile();
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : '롤백 실패', 'error');
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
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl border shadow-lg px-5 py-3 text-sm ${
            saveMsgType === 'error'
              ? 'border-red-200 bg-red-50 text-red-700'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700'
          }`}
        >
          {saveMsg}
        </motion.div>
      )}
    </div>
  );
}
