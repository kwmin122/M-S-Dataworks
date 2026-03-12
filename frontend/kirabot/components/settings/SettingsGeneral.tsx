import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCircle, XCircle, Sparkles } from 'lucide-react';
import { getApiBaseUrl } from '../../services/kiraApiService';
import { useUser } from '../../context/UserContext';
import { getAlertSessionId } from '../../utils/alertSessionId';

const SCHEDULES: Record<string, string> = {
  realtime: '30분마다 확인',
  daily_1: '하루 1번',
  daily_2: '하루 2번',
  daily_3: '하루 3번',
};

interface AlertSummary {
  enabled: boolean;
  email: string;
  schedule: string;
  rules: { keywords?: string[]; enabled?: boolean }[];
}

interface SettingsGeneralProps {
  user?: { name: string; email: string; avatarUrl?: string } | null;
}

const SettingsGeneral: React.FC<SettingsGeneralProps> = ({ user }) => {
  const navigate = useNavigate();
  const ctxUser = useUser();
  const [alert, setAlert] = useState<AlertSummary | null>(null);
  const [loadingAlert, setLoadingAlert] = useState(true);
  const [usePack, setUsePack] = useState(() => localStorage.getItem('kira_use_pack') === 'true');

  const handleTogglePack = (enabled: boolean) => {
    localStorage.setItem('kira_use_pack', enabled ? 'true' : 'false');
    setUsePack(enabled);
  };

  useEffect(() => {
    const uid = ctxUser?.id;
    if (!uid) { setLoadingAlert(false); return; }
    let cancelled = false;
    const sid = getAlertSessionId(uid);
    fetch(`${getApiBaseUrl()}/api/alerts/config?session_id=${sid}`)
      .then(r => r.json())
      .then(data => {
        if (!cancelled && data.email) setAlert(data);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoadingAlert(false); });
    return () => { cancelled = true; };
  }, [ctxUser?.id]);

  const handleDisableAlert = async () => {
    const uid = ctxUser?.id;
    if (!uid || !alert) return;
    if (!confirm('알림을 해제하시겠습니까?')) return;
    const sid = getAlertSessionId(uid);
    try {
      await fetch(`${getApiBaseUrl()}/api/alerts/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sid,
          enabled: false,
          email: alert.email,
          schedule: alert.schedule,
          hours: [],
          rules: alert.rules,
        }),
      });
      setAlert(prev => prev ? { ...prev, enabled: false } : null);
    } catch {
      window.alert('해제 실패');
    }
  };

  const activeRules = alert?.rules?.filter(r => r.enabled !== false) || [];
  const ruleKeywords = activeRules
    .flatMap(r => r.keywords || [])
    .slice(0, 3);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">프로필</h2>
        <div className="flex items-center gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
          {user?.avatarUrl ? (
            <img src={user.avatarUrl} alt="" className="h-14 w-14 rounded-full" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-kira-100 text-lg font-bold text-kira-600">
              {user?.name?.charAt(0) || '?'}
            </div>
          )}
          <div>
            <p className="text-base font-medium text-slate-900">{user?.name || '사용자'}</p>
            <p className="text-sm text-slate-500">{user?.email || ''}</p>
          </div>
        </div>
      </div>

      {/* 알림 설정 요약 */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">공고 알림</h2>
        {loadingAlert ? (
          <div className="rounded-xl border border-slate-200 p-4">
            <div className="animate-pulse h-12 bg-slate-100 rounded" />
          </div>
        ) : alert ? (
          <div className={`rounded-xl border p-4 ${alert.enabled ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50'}`}>
            <div className="flex items-start gap-3">
              {alert.enabled ? (
                <CheckCircle size={20} className="text-emerald-600 mt-0.5 flex-shrink-0" />
              ) : (
                <XCircle size={20} className="text-slate-400 mt-0.5 flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-900">
                  {alert.enabled ? '알림 활성화됨' : '알림 비활성화됨'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {alert.email} · {SCHEDULES[alert.schedule] || alert.schedule} · 규칙 {activeRules.length}개
                </p>
                {ruleKeywords.length > 0 && (
                  <p className="text-xs text-slate-400 mt-1">
                    키워드: {ruleKeywords.join(', ')}
                  </p>
                )}
                <div className="flex gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => navigate('/settings/alerts')}
                    className="rounded-lg border border-kira-300 bg-white px-3 py-1.5 text-xs font-medium text-kira-700 hover:bg-kira-50 transition-colors"
                  >
                    알림 설정 변경
                  </button>
                  {alert.enabled && (
                    <button
                      type="button"
                      onClick={handleDisableAlert}
                      className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      알림 해제
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200 p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Bell size={20} className="text-slate-400" />
              <p className="text-sm text-slate-500">알림이 설정되지 않았습니다.</p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/settings/alerts')}
              className="rounded-lg bg-kira-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-kira-700 transition-colors"
            >
              알림 설정하기
            </button>
          </div>
        )}
      </div>

      {/* AI 생성 엔진 */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">AI 생성 엔진</h2>
        <div className="rounded-xl border border-slate-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Sparkles size={18} className={usePack ? 'text-kira-600' : 'text-slate-400'} />
              <div>
                <p className="text-sm font-medium text-slate-700">도메인별 Pack 엔진 사용</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {usePack
                    ? 'IT/연구/컨설팅/교육 도메인 자동 감지 + 전문 템플릿으로 생성'
                    : '범용 엔진으로 생성 (기본)'}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => handleTogglePack(!usePack)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                usePack ? 'bg-kira-600' : 'bg-slate-300'
              }`}
              role="switch"
              aria-checked={usePack}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  usePack ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">모양</h2>
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-sm font-medium text-slate-700 mb-3">테마</p>
          <div className="flex gap-3">
            {(['시스템', '라이트', '다크'] as const).map((label) => (
              <label key={label} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="theme"
                  value={label}
                  defaultChecked={label === '라이트'}
                  className="text-kira-600 focus:ring-kira-500"
                />
                <span className="text-sm text-slate-700">{label}</span>
              </label>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-2">테마 기능은 추후 지원 예정입니다.</p>
        </div>
      </div>
    </div>
  );
};

export default SettingsGeneral;
