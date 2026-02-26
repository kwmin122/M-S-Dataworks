import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Bell, Plus, Trash2, Save, CheckCircle, XCircle } from 'lucide-react';
import { getApiBaseUrl } from '../../services/kiraApiService';
import { useUser } from '../../context/UserContext';
import { getAlertSessionId } from '../../utils/alertSessionId';
import ChipInput from '../shared/ChipInput';
import Toggle from '../shared/Toggle';
import { pageTransition } from '../../utils/animations';
import { REGIONS } from '../../constants/filters';

const LEGACY_ALERT_SESSION_KEY = 'kirabot_alert_session_id';

interface AlertRule {
  id: string;
  keywords: string[];
  excludeKeywords: string[];
  categories: string[];
  regions: string[];
  minAmt: string;
  maxAmt: string;
  enabled: boolean;
}

const CATEGORIES = ['물품', '용역', '공사', '외자', '기타'];
const SCHEDULES = [
  { value: 'realtime', label: '30분마다 확인' },
  { value: 'daily_1', label: '하루 1번' },
  { value: 'daily_2', label: '하루 2번' },
  { value: 'daily_3', label: '하루 3번' },
];

const HOUR_OPTIONS = Array.from({ length: 15 }, (_, i) => i + 7); // 7시~21시
const DEFAULT_HOURS: Record<string, number[]> = {
  daily_1: [9],
  daily_2: [9, 18],
  daily_3: [9, 13, 18],
};

function createEmptyRule(): AlertRule {
  return {
    id: `rule_${Date.now()}`,
    keywords: [],
    excludeKeywords: [],
    categories: [],
    regions: [],
    minAmt: '',
    maxAmt: '',
    enabled: true,
  };
}

const AlertSettingsPage: React.FC = () => {
  const user = useUser();
  const sessionId = useMemo(() => user?.id ? getAlertSessionId(user.id) : '', [user?.id]);

  const [globalEnabled, setGlobalEnabled] = useState(true);
  const [email, setEmail] = useState('');
  const [schedule, setSchedule] = useState('daily_1');
  const [hours, setHours] = useState<number[]>([9]);
  const [rules, setRules] = useState<AlertRule[]>([createEmptyRule()]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [hasSavedConfig, setHasSavedConfig] = useState(false);
  const [loading, setLoading] = useState(true);

  const addRule = () => setRules(prev => [...prev, createEmptyRule()]);
  const removeRule = (id: string) => setRules(prev => prev.filter(r => r.id !== id));
  const updateRule = useCallback((id: string, updates: Partial<AlertRule>) => {
    setRules(prev => prev.map(r => r.id === id ? { ...r, ...updates } : r));
  }, []);

  const toggleAllCategories = useCallback((ruleId: string, currentCategories: string[]) => {
    const allSelected = currentCategories.length === CATEGORIES.length;
    updateRule(ruleId, { categories: allSelected ? [] : [...CATEGORIES] });
  }, [updateRule]);

  const toggleAllRegions = useCallback((ruleId: string, currentRegions: string[]) => {
    const allSelected = currentRegions.length === REGIONS.length;
    updateRule(ruleId, { regions: allSelected ? [] : [...REGIONS] });
  }, [updateRule]);

  const handleScheduleChange = useCallback((newSchedule: string) => {
    setSchedule(newSchedule);
    if (newSchedule in DEFAULT_HOURS) {
      setHours(DEFAULT_HOURS[newSchedule]);
    } else {
      setHours([]);
    }
  }, []);

  const requiredHourCount = schedule === 'daily_1' ? 1 : schedule === 'daily_2' ? 2 : schedule === 'daily_3' ? 3 : 0;

  const toggleHour = useCallback((hour: number) => {
    setHours(prev => {
      if (prev.includes(hour)) {
        return prev.filter(h => h !== hour);
      }
      if (requiredHourCount > 0 && prev.length >= requiredHourCount) {
        return [...prev.slice(1), hour].sort((a, b) => a - b);
      }
      return [...prev, hour].sort((a, b) => a - b);
    });
  }, [requiredHourCount]);

  // Load existing config on mount (with migration from legacy random UUID)
  useEffect(() => {
    if (!sessionId) { setLoading(false); return; }

    const applyConfig = (data: any) => {
      if (data.email) { setEmail(data.email); setHasSavedConfig(true); }
      if (data.schedule) setSchedule(data.schedule);
      if (Array.isArray(data.hours) && data.hours.length > 0) {
        setHours(data.hours.map(Number));
      } else if (data.schedule && data.schedule in DEFAULT_HOURS) {
        setHours(DEFAULT_HOURS[data.schedule as keyof typeof DEFAULT_HOURS]);
      }
      if (typeof data.enabled === 'boolean') setGlobalEnabled(data.enabled);
      if (Array.isArray(data.rules) && data.rules.length > 0) {
        setRules(data.rules.map((r: any, i: number) => ({
          id: `rule_${i}`,
          keywords: r.keywords || [],
          excludeKeywords: r.excludeKeywords || [],
          categories: r.categories || [],
          regions: r.regions || [],
          minAmt: r.minAmt ? String(r.minAmt) : '',
          maxAmt: r.maxAmt ? String(r.maxAmt) : '',
          enabled: r.enabled ?? true,
        })));
        setHasSavedConfig(true);
      }
    };

    const baseUrl = getApiBaseUrl();

    fetch(`${baseUrl}/api/alerts/config?session_id=${sessionId}`)
      .then(res => res.json())
      .then(async (data) => {
        if (data.email) {
          applyConfig(data);
          return;
        }
        // No config for user-scoped ID — try migrating from legacy random UUID
        const legacyId = localStorage.getItem(LEGACY_ALERT_SESSION_KEY);
        if (legacyId) {
          try {
            const legacyRes = await fetch(`${baseUrl}/api/alerts/config?session_id=${legacyId}`);
            const legacyData = await legacyRes.json();
            if (legacyData.email) {
              // Migrate: save under new user-scoped session ID
              await fetch(`${baseUrl}/api/alerts/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...legacyData, session_id: sessionId }),
              });
              applyConfig(legacyData);
              localStorage.removeItem(LEGACY_ALERT_SESSION_KEY);
              return;
            }
          } catch { /* migration failed, continue with empty */ }
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [sessionId]);

  const handleSave = async () => {
    if (!email.trim()) {
      alert('수신 이메일을 입력해주세요.');
      return;
    }
    setSaving(true);
    setSaved(false);
    setSaveMsg('');
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/alerts/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          enabled: globalEnabled,
          email: email.trim(),
          schedule,
          hours: schedule === 'realtime' ? [] : hours,
          rules: rules.map(r => ({
            keywords: r.keywords,
            excludeKeywords: r.excludeKeywords,
            categories: r.categories,
            regions: r.regions,
            minAmt: r.minAmt ? Number(r.minAmt) : undefined,
            maxAmt: r.maxAmt ? Number(r.maxAmt) : undefined,
            enabled: r.enabled,
          })),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '저장 실패');
      setSaved(true);
      setHasSavedConfig(true);

      // 상세 안내 토스트 생성
      const activeRules = rules.filter(r => r.enabled);
      const allKeywords = activeRules.flatMap(r => r.keywords);
      const allRegions = activeRules.flatMap(r => r.regions);
      const allCats = activeRules.flatMap(r => r.categories);
      const scheduleInfo = schedule === 'realtime' ? '30분마다 확인'
        : `하루 ${hours.length}번 (${hours.map(h => `${h}시`).join(', ')})`;
      const lines = [
        '알림 설정이 완료되었습니다!',
        allKeywords.length > 0 ? `키워드: ${allKeywords.join(', ')}` : '',
        `업무구분: ${allCats.length > 0 ? allCats.join(', ') : '전체'}`,
        `지역: ${allRegions.length > 0 ? allRegions.join(', ') : '전체'}`,
        `이메일: ${email}`,
        `수신 방식: ${scheduleInfo}`,
        '곧 맞춤 공고를 메일로 보내드릴게요',
      ].filter(Boolean).join('\n');
      setSaveMsg(lines);

      setTimeout(() => { setSaved(false); setSaveMsg(''); }, 5000);
    } catch (e) {
      alert(e instanceof Error ? e.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('알림 설정을 삭제하시겠습니까?')) return;
    try {
      await fetch(`${getApiBaseUrl()}/api/alerts/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          enabled: false,
          email: '',
          schedule: 'daily_1',
          hours: [],
          rules: [],
        }),
      });
      setEmail('');
      setSchedule('daily_1');
      setGlobalEnabled(true);
      setRules([createEmptyRule()]);
      setHasSavedConfig(false);
      setSaveMsg('');
      setSaved(false);
    } catch {
      alert('삭제 실패');
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-kira-600" />
      </div>
    );
  }

  const scheduleLabel = SCHEDULES.find(s => s.value === schedule)?.label || schedule;

  return (
    <motion.div
      className="flex-1 overflow-y-auto p-6 lg:p-8"
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-slate-900">알림 설정</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-500">자동 알림</span>
            <Toggle enabled={globalEnabled} onChange={setGlobalEnabled} label="자동 알림" />
          </div>
        </div>

        {/* Current Alert Status */}
        {hasSavedConfig && (
          <div className={`rounded-xl border p-4 mb-4 ${globalEnabled ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50'}`}>
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                {globalEnabled ? (
                  <CheckCircle size={20} className="text-emerald-600 mt-0.5 flex-shrink-0" />
                ) : (
                  <XCircle size={20} className="text-slate-400 mt-0.5 flex-shrink-0" />
                )}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    {globalEnabled ? '알림 활성화됨' : '알림 비활성화됨'}
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    {email} · {scheduleLabel}
                    {schedule !== 'realtime' && hours.length > 0 && ` (${hours.map(h => `${h}시`).join(', ')})`}
                    {' · '}규칙 {rules.filter(r => r.enabled).length}개 활성
                  </p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {rules.filter(r => r.enabled).map((r, i) => (
                      <span key={r.id} className="inline-flex items-center rounded-full bg-white border border-slate-200 px-2 py-0.5 text-xs text-slate-600">
                        {r.keywords.length > 0 ? r.keywords.slice(0, 2).join(', ') : '전체 키워드'}
                        {r.keywords.length > 2 && ` +${r.keywords.length - 2}`}
                        {r.regions.length > 0 && ` · ${r.regions.length === REGIONS.length ? '전체 지역' : r.regions.slice(0, 2).join(', ')}${r.regions.length > 2 ? ` +${r.regions.length - 2}` : ''}`}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={handleDelete}
                className="text-xs text-slate-400 hover:text-red-500 whitespace-nowrap"
              >
                설정 삭제
              </button>
            </div>
          </div>
        )}

        {/* Email & Schedule */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 mb-4">
          <h2 className="text-base font-semibold text-slate-900 mb-4">수신 설정</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">수신 이메일</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="email@example.com"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">수신 빈도</label>
              <select
                value={schedule}
                onChange={e => handleScheduleChange(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none"
              >
                {SCHEDULES.map(s => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
          {/* 시간대 선택 (daily_N 일 때만) */}
          {requiredHourCount > 0 && (
            <div className="mt-4">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                발송 시간 ({requiredHourCount}개 선택)
              </label>
              <div className="flex flex-wrap gap-1.5">
                {HOUR_OPTIONS.map(h => (
                  <button
                    key={h}
                    type="button"
                    onClick={() => toggleHour(h)}
                    className={`rounded-lg px-2.5 py-1 text-xs font-medium border transition-colors ${
                      hours.includes(h)
                        ? 'border-kira-600 bg-kira-600 text-white'
                        : 'border-slate-300 text-slate-600 hover:border-kira-400 hover:bg-kira-50'
                    }`}
                  >
                    {String(h).padStart(2, '0')}시
                  </button>
                ))}
              </div>
              {hours.length < requiredHourCount && (
                <p className="text-xs text-amber-500 mt-1">
                  {requiredHourCount - hours.length}개 더 선택해주세요
                </p>
              )}
              {hours.length > 0 && (
                <p className="text-xs text-slate-400 mt-1">
                  선택: {hours.map(h => `${String(h).padStart(2, '0')}시`).join(', ')}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Alert Rules */}
        <div className="space-y-3 mb-4">
          {rules.map((rule, idx) => (
            <div key={rule.id} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">규칙 {idx + 1}</h3>
                  <Toggle enabled={rule.enabled} onChange={v => updateRule(rule.id, { enabled: v })} />
                </div>
                {rules.length > 1 && (
                  <button type="button" onClick={() => removeRule(rule.id)} className="text-slate-400 hover:text-red-500">
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
              <div className="space-y-4">
                <ChipInput label="포함 키워드" chips={rule.keywords} onChange={v => updateRule(rule.id, { keywords: v })} placeholder="예: 소프트웨어, IT" />
                <ChipInput label="제외 키워드" chips={rule.excludeKeywords} onChange={v => updateRule(rule.id, { excludeKeywords: v })} placeholder="예: 시설, 건축" />
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-sm font-medium text-slate-700">업무구분</label>
                    <button
                      type="button"
                      onClick={() => toggleAllCategories(rule.id, rule.categories)}
                      className="text-xs text-kira-600 hover:text-kira-700 font-medium"
                    >
                      {rule.categories.length === CATEGORIES.length ? '전체 해제' : '전체 선택'}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {CATEGORIES.map(cat => (
                      <button
                        key={cat}
                        type="button"
                        onClick={() => {
                          const cats = rule.categories.includes(cat) ? rule.categories.filter(c => c !== cat) : [...rule.categories, cat];
                          updateRule(rule.id, { categories: cats });
                        }}
                        className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                          rule.categories.includes(cat)
                            ? 'border-kira-600 bg-kira-600 text-white'
                            : 'border-slate-300 text-slate-600 hover:border-kira-400 hover:bg-kira-50'
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                  {rule.categories.length === 0 && <p className="text-xs text-slate-400 mt-1">선택 안하면 전체</p>}
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-sm font-medium text-slate-700">지역</label>
                    <button
                      type="button"
                      onClick={() => toggleAllRegions(rule.id, rule.regions)}
                      className="text-xs text-kira-600 hover:text-kira-700 font-medium"
                    >
                      {rule.regions.length === REGIONS.length ? '전체 해제' : '전체 선택'}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {REGIONS.map(rgn => (
                      <button
                        key={rgn}
                        type="button"
                        onClick={() => {
                          const regions = rule.regions.includes(rgn) ? rule.regions.filter(r => r !== rgn) : [...rule.regions, rgn];
                          updateRule(rule.id, { regions });
                        }}
                        className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                          rule.regions.includes(rgn)
                            ? 'border-kira-600 bg-kira-600 text-white'
                            : 'border-slate-300 text-slate-600 hover:border-kira-400 hover:bg-kira-50'
                        }`}
                      >
                        {rgn}
                      </button>
                    ))}
                  </div>
                  {rule.regions.length === 0 && <p className="text-xs text-slate-400 mt-1">선택 안하면 전체</p>}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">최소 금액 (원)</label>
                    <input type="number" value={rule.minAmt} onChange={e => updateRule(rule.id, { minAmt: e.target.value })} placeholder="0" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">최대 금액 (원)</label>
                    <input type="number" value={rule.maxAmt} onChange={e => updateRule(rule.id, { maxAmt: e.target.value })} placeholder="10,000,000,000" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add Rule + Actions */}
        <div className="flex items-center justify-between">
          <button type="button" onClick={addRule} className="flex items-center gap-1.5 text-sm font-medium text-kira-600 hover:text-kira-700">
            <Plus size={16} /> 규칙 추가
          </button>
          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSave} disabled={saving} className="flex items-center gap-1.5 rounded-lg bg-kira-600 px-4 py-2 text-sm font-medium text-white hover:bg-kira-700 disabled:opacity-50 transition-colors">
              <Save size={16} /> {saving ? '저장 중...' : saved ? '저장됨!' : '저장'}
            </button>
          </div>
        </div>

        {/* 저장 완료 토스트 */}
        {saveMsg && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl border border-emerald-200 bg-emerald-50 shadow-lg px-5 py-4 max-w-md"
          >
            {saveMsg.split('\n').map((line, i) => (
              <p key={i} className={`text-sm ${i === 0 ? 'font-semibold text-emerald-800 mb-1.5' : i === saveMsg.split('\n').length - 1 ? 'text-emerald-600 mt-1.5 font-medium' : 'text-emerald-700'}`}>
                {line}
              </p>
            ))}
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};

export default AlertSettingsPage;
