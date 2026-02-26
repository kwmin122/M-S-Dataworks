import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Bell, Plus, Trash2, Save } from 'lucide-react';
import { useChatContext } from '../../context/ChatContext';
import { getApiBaseUrl } from '../../services/kiraApiService';
import ChipInput from '../shared/ChipInput';
import Toggle from '../shared/Toggle';
import EmptyState from '../shared/EmptyState';
import { pageTransition } from '../../utils/animations';
import { REGIONS } from '../../constants/filters';

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
  { value: 'realtime', label: '공고 등록 즉시' },
  { value: 'daily_1', label: '하루 1번' },
  { value: 'daily_2', label: '하루 2번' },
  { value: 'daily_3', label: '하루 3번' },
];

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
  const { state } = useChatContext();
  const navigate = useNavigate();
  const activeConv = state.conversations.find(c => c.id === state.activeConversationId);
  const sessionId = activeConv?.sessionId;

  const [globalEnabled, setGlobalEnabled] = useState(true);
  const [email, setEmail] = useState('');
  const [schedule, setSchedule] = useState('daily_1');
  const [rules, setRules] = useState<AlertRule[]>([createEmptyRule()]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  const addRule = () => setRules(prev => [...prev, createEmptyRule()]);
  const removeRule = (id: string) => setRules(prev => prev.filter(r => r.id !== id));
  const updateRule = useCallback((id: string, updates: Partial<AlertRule>) => {
    setRules(prev => prev.map(r => r.id === id ? { ...r, ...updates } : r));
  }, []);

  // Load existing config on mount
  useEffect(() => {
    if (!sessionId) return;
    fetch(`${getApiBaseUrl()}/api/alerts/config?session_id=${sessionId}`)
      .then(res => res.json())
      .then(data => {
        if (data.email) setEmail(data.email);
        if (data.schedule) setSchedule(data.schedule);
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
        }
      })
      .catch(() => {});
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
          hours: [],
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
      if (data.confirmationSent) {
        setSaveMsg(`저장 완료! ${email}으로 확인 이메일을 보내드렸습니다.`);
      } else {
        setSaveMsg('저장 완료!');
      }
      setTimeout(() => { setSaved(false); setSaveMsg(''); }, 5000);
    } catch (e) {
      alert(e instanceof Error ? e.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  if (!sessionId) {
    return (
      <div className="flex-1">
        <EmptyState
          icon={Bell}
          title="세션이 필요합니다"
          description="채팅에서 먼저 공고를 검색하면 알림 설정을 할 수 있어요."
          actionLabel="채팅으로 이동"
          onAction={() => navigate('/chat')}
        />
      </div>
    );
  }

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
                onChange={e => setSchedule(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none"
              >
                {SCHEDULES.map(s => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
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
                  <label className="block text-sm font-medium text-slate-700 mb-1">업무구분</label>
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
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">지역</label>
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
            {saveMsg && <span className="text-sm text-emerald-600">{saveMsg}</span>}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default AlertSettingsPage;
