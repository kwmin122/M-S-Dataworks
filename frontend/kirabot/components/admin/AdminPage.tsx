import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3, Bell, Trash2, Send, RefreshCw, Users, MessageSquare,
  FileSearch, Activity, CheckCircle2, XCircle, DollarSign,
  AlertTriangle, Timer, Clock, TrendingUp,
} from 'lucide-react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  getAdminMetrics,
  type AdminMetrics,
  type EventTypeMetrics,
} from '../../services/studioApi';
import {
  getAdminUsage,
  getAdminAlerts,
  deleteAdminAlert,
  sendAdminAlertNow,
  type AdminUsageResponse,
  type AdminAlertItem,
} from '../../services/kiraApiService';

type Tab = 'kpi' | 'usage' | 'alerts';
type PeriodOption = 7 | 30 | 90;

const PERIOD_OPTIONS: { value: PeriodOption; label: string }[] = [
  { value: 7, label: '7일' },
  { value: 30, label: '30일' },
  { value: 90, label: '90일' },
];

const EVENT_TYPE_LABELS: Record<string, string> = {
  generate: '생성',
  analyze: '분석',
  classify: '분류',
  upload: '업로드',
  search: '검색',
  relearn: '재학습',
  download: '다운로드',
};

const DOC_TYPE_LABELS: Record<string, string> = {
  proposal: '제안서',
  execution_plan: '실행계획',
  presentation: '발표자료',
  track_record: '실적기술서',
  checklist: '체크리스트',
};

const AdminPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('kpi');

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* Header */}
      <div className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-lg font-bold text-slate-800">관리자</h1>
        <div className="mt-3 flex gap-1">
          {([
            { key: 'kpi' as Tab, label: 'KPI 대시보드', icon: TrendingUp },
            { key: 'usage' as Tab, label: '사용량', icon: BarChart3 },
            { key: 'alerts' as Tab, label: '알림 관리', icon: Bell },
          ]).map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                tab === key ? 'bg-primary-50 text-primary-700' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
              }`}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {tab === 'kpi' ? <KpiDashboard /> : tab === 'usage' ? <UsagePanel /> : <AlertsPanel />}
      </div>
    </div>
  );
};

// ── KPI Dashboard ──

const KpiDashboard: React.FC = () => {
  const [data, setData] = useState<AdminMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState<PeriodOption>(30);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getAdminMetrics(days);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '메트릭 데이터를 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorCard message={error} onRetry={load} />;
  if (!data) return null;

  const { summary, by_event_type, by_doc_type, cost, quality, daily_trend } = data;

  // Compute average generation time across all event types
  const allDurations = Object.values(by_event_type);
  const avgGenTime = allDurations.length > 0
    ? allDurations.reduce((sum, m) => sum + m.avg_duration_ms * m.count, 0) /
      allDurations.reduce((sum, m) => sum + m.count, 0)
    : 0;

  // Prepare event type chart data
  const eventTypeChartData = Object.entries(by_event_type)
    .sort(([, a], [, b]) => b.count - a.count)
    .map(([type, metrics]) => ({
      name: EVENT_TYPE_LABELS[type] || type,
      success: metrics.success,
      failure: metrics.failure,
      avgMs: metrics.avg_duration_ms,
    }));

  return (
    <div className="space-y-6">
      {/* Period selector + refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-slate-500" />
          <span className="text-sm font-semibold text-slate-700">KPI 대시보드</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-slate-200 bg-white">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setDays(opt.value)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors first:rounded-l-lg last:rounded-r-lg ${
                  days === opt.value
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            title="새로고침"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Section 1: Summary Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryCard
          label="총 이벤트"
          value={summary.total_events.toLocaleString()}
          sub={`성공 ${summary.success_count.toLocaleString()} / 실패 ${summary.failure_count.toLocaleString()}`}
          icon={Activity}
          color="blue"
        />
        <SummaryCard
          label="성공률"
          value={`${(summary.success_rate * 100).toFixed(1)}%`}
          sub={`타임아웃 ${summary.timeout_count}건`}
          icon={CheckCircle2}
          color="emerald"
        />
        <SummaryCard
          label="총 비용"
          value={`$${cost.total_usd.toFixed(2)}`}
          sub={`${Object.keys(cost.by_model).length}개 모델`}
          icon={DollarSign}
          color="amber"
        />
        <SummaryCard
          label="평균 소요 시간"
          value={`${(avgGenTime / 1000).toFixed(1)}초`}
          sub={`${allDurations.length}개 유형 평균`}
          icon={Timer}
          color="purple"
        />
      </div>

      {/* Section 2: Daily Trend Chart */}
      {daily_trend.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="mb-4 flex items-center gap-2">
            <Clock size={15} className="text-slate-500" />
            <span className="text-sm font-semibold text-slate-700">일별 추이</span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={daily_trend} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickFormatter={(v: string) => v.slice(5)}
                />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                    fontSize: '12px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                  }}
                  labelFormatter={(label: string) => `날짜: ${label}`}
                />
                <Legend
                  wrapperStyle={{ fontSize: '12px' }}
                  iconType="circle"
                  iconSize={8}
                />
                <Line
                  type="monotone"
                  dataKey="events"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#3b82f6' }}
                  name="전체"
                />
                <Line
                  type="monotone"
                  dataKey="success"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#10b981' }}
                  name="성공"
                />
                <Line
                  type="monotone"
                  dataKey="failure"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#ef4444' }}
                  name="실패"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Section 3: Event Type Breakdown */}
      {eventTypeChartData.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Bar chart */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="mb-4">
              <span className="text-sm font-semibold text-slate-700">이벤트 유형별</span>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={eventTypeChartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                  <Tooltip
                    contentStyle={{
                      borderRadius: '8px',
                      border: '1px solid #e2e8f0',
                      fontSize: '12px',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '12px' }} iconType="circle" iconSize={8} />
                  <Bar dataKey="success" fill="#10b981" name="성공" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="failure" fill="#ef4444" name="실패" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Event type detail table */}
          <div className="rounded-xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-4 py-3">
              <span className="text-sm font-semibold text-slate-700">이벤트 상세</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                    <th className="px-4 py-2">유형</th>
                    <th className="px-4 py-2 text-right">횟수</th>
                    <th className="px-4 py-2 text-right">성공</th>
                    <th className="px-4 py-2 text-right">실패</th>
                    <th className="px-4 py-2 text-right">평균(ms)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(by_event_type)
                    .sort(([, a], [, b]) => b.count - a.count)
                    .map(([type, metrics]) => (
                      <tr key={type} className="border-b border-slate-50 last:border-b-0 hover:bg-slate-50/50">
                        <td className="px-4 py-2 font-medium text-slate-700">
                          {EVENT_TYPE_LABELS[type] || type}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                          {metrics.count.toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-emerald-600">
                          {metrics.success.toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-red-500">
                          {metrics.failure.toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                          {metrics.avg_duration_ms.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Section 4: Document Type Stats */}
      {Object.keys(by_doc_type).length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3 flex items-center gap-2">
            <Timer size={15} className="text-slate-500" />
            <span className="text-sm font-semibold text-slate-700">문서 유형별 생성 현황</span>
          </div>
          <div className="p-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(by_doc_type)
              .sort(([, a], [, b]) => b.count - a.count)
              .map(([docType, m]) => {
                const targetMs: Record<string, number> = {
                  proposal: 180000,
                  execution_plan: 120000,
                  track_record: 60000,
                  presentation: 120000,
                };
                const target = targetMs[docType] || 180000;
                const avgSec = m.avg_duration_ms / 1000;
                const targetSec = target / 1000;
                const withinTarget = m.avg_duration_ms <= target;
                const pct = Math.min((m.avg_duration_ms / target) * 100, 100);
                return (
                  <div key={docType} className="rounded-lg border border-slate-100 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-slate-700">
                        {DOC_TYPE_LABELS[docType] || docType}
                      </span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        withinTarget
                          ? 'bg-green-50 text-green-700'
                          : 'bg-amber-50 text-amber-700'
                      }`}>
                        {withinTarget ? '목표 이내' : '목표 초과'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            withinTarget ? 'bg-green-400' : 'bg-amber-400'
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>평균 {avgSec.toFixed(1)}초</span>
                      <span>목표 {targetSec.toFixed(0)}초</span>
                    </div>
                    <div className="text-xs text-slate-400 mt-1">{m.count}건 생성</div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Section 5: Cost by Model */}
      {Object.keys(cost.by_model).length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3 flex items-center gap-2">
            <DollarSign size={15} className="text-slate-500" />
            <span className="text-sm font-semibold text-slate-700">모델별 비용</span>
            <span className="ml-auto text-xs font-medium text-slate-400">
              총 ${cost.total_usd.toFixed(4)}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                  <th className="px-4 py-2">모델</th>
                  <th className="px-4 py-2 text-right">토큰</th>
                  <th className="px-4 py-2 text-right">비용 (USD)</th>
                  <th className="px-4 py-2 w-32">비중</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(cost.by_model)
                  .sort(([, a], [, b]) => b.cost_usd - a.cost_usd)
                  .map(([model, m]) => {
                    const pct = cost.total_usd > 0 ? (m.cost_usd / cost.total_usd) * 100 : 0;
                    return (
                      <tr key={model} className="border-b border-slate-50 last:border-b-0 hover:bg-slate-50/50">
                        <td className="px-4 py-2 font-medium text-slate-700 font-mono text-xs">{model}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                          {m.tokens.toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                          ${m.cost_usd.toFixed(4)}
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                              <div
                                className="h-full rounded-full bg-amber-400 transition-all"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span className="text-[10px] tabular-nums text-slate-400 w-10 text-right">
                              {pct.toFixed(1)}%
                            </span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Section 6: Quality Summary */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-4 flex items-center gap-2">
          <AlertTriangle size={15} className="text-amber-500" />
          <span className="text-sm font-semibold text-slate-700">품질 신호</span>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-slate-100 p-4 text-center">
            <p className="text-xs font-medium text-slate-500">수동 오버라이드</p>
            <p className="mt-2 text-2xl font-bold tabular-nums text-slate-800">{quality.override_count}</p>
            <p className="mt-1 text-[11px] text-slate-400">사용자가 AI 분류를 수정한 횟수</p>
          </div>
          <div className="rounded-lg border border-slate-100 p-4 text-center">
            <p className="text-xs font-medium text-slate-500">저신뢰도 분류</p>
            <p className="mt-2 text-2xl font-bold tabular-nums text-slate-800">{quality.low_confidence_count}</p>
            <p className="mt-1 text-[11px] text-slate-400">신뢰도 0.5 미만 분류 건수</p>
          </div>
          <div className="rounded-lg border border-slate-100 p-4 text-center">
            <p className="text-xs font-medium text-slate-500">평균 품질 점수</p>
            <p className="mt-2 text-2xl font-bold tabular-nums text-slate-800">
              {quality.avg_quality_score !== null ? quality.avg_quality_score.toFixed(1) : '-'}
            </p>
            <p className="mt-1 text-[11px] text-slate-400">생성 문서 품질 평균</p>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Usage Dashboard (legacy) ──

const UsagePanel: React.FC = () => {
  const [data, setData] = useState<AdminUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getAdminUsage();
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '사용량 데이터를 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorCard message={error} onRetry={load} />;
  if (!data) return null;

  const { overview, by_actor } = data;

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="오늘 채팅" value={overview.today_chat} icon={MessageSquare} color="blue" />
        <StatCard label="오늘 분석" value={overview.today_analyze} icon={FileSearch} color="emerald" />
        <StatCard label="월간 채팅" value={overview.month_chat} icon={MessageSquare} color="indigo" />
        <StatCard label="월간 분석" value={overview.month_analyze} icon={FileSearch} color="purple" />
      </div>

      {/* User table */}
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
          <Users size={16} className="text-slate-400" />
          <span className="text-sm font-semibold text-slate-700">사용자별 ({by_actor.length}명)</span>
          <button type="button" onClick={() => void load()} className="ml-auto rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" title="새로고침">
            <RefreshCw size={14} />
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                <th className="px-4 py-2">사용자</th>
                <th className="px-4 py-2 text-right">채팅</th>
                <th className="px-4 py-2 text-right">분석</th>
                <th className="px-4 py-2 text-right">최근 활동</th>
              </tr>
            </thead>
            <tbody>
              {by_actor.map((actor) => (
                <tr key={actor.actor_key} className="border-b border-slate-50 last:border-b-0 hover:bg-slate-25">
                  <td className="px-4 py-2">
                    <span className="font-medium text-slate-700">{actor.username || actor.actor_key}</span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-slate-600">{actor.chat_count}</td>
                  <td className="px-4 py-2 text-right tabular-nums text-slate-600">{actor.analyze_count}</td>
                  <td className="px-4 py-2 text-right text-xs text-slate-400">{formatRelativeTime(actor.last_activity)}</td>
                </tr>
              ))}
              {by_actor.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-400">사용 기록이 없습니다.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ── Alerts Management ──

const AlertsPanel: React.FC = () => {
  const [alerts, setAlerts] = useState<AdminAlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [sendResult, setSendResult] = useState<string>('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getAdminAlerts();
      setAlerts(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '알림 목록을 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm(`알림 설정 "${id}"을(를) 삭제하시겠습니까?`)) return;
    try {
      await deleteAdminAlert(id);
      setAlerts((prev) => prev.filter((a) => a.session_id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : '삭제 실패');
    }
  }, []);

  const handleSendNow = useCallback(async (id: string) => {
    setSendingId(id);
    setSendResult('');
    try {
      const res = await sendAdminAlertNow(id);
      if (res.sent) {
        setSendResult(`${res.count}건 발송 완료`);
      } else {
        setSendResult(res.reason || '발송할 공고가 없습니다.');
      }
      void load();
    } catch (e) {
      setSendResult(e instanceof Error ? e.message : '발송 실패');
    } finally {
      setSendingId(null);
    }
  }, [load]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorCard message={error} onRetry={load} />;

  const scheduleLabel = (s: string, hours: number[]) => {
    if (s === 'realtime') return '실시간 (30분)';
    if (s === 'hourly') return '매시 (8-20시)';
    if (hours.length > 0) return `매일 ${hours.map(h => `${h}시`).join(', ')}`;
    if (s === 'daily_2') return '매일 9시, 18시';
    if (s === 'daily_3') return '매일 9시, 13시, 18시';
    return '매일 9시';
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-700">알림 설정 ({alerts.length}건)</span>
        <button type="button" onClick={() => void load()} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" title="새로고침">
          <RefreshCw size={14} />
        </button>
      </div>

      {sendResult && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm text-blue-700">
          {sendResult}
        </div>
      )}

      {alerts.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white px-6 py-12 text-center text-slate-400">
          등록된 알림 설정이 없습니다.
        </div>
      )}

      {alerts.map((alert) => (
        <div key={alert.session_id} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  alert.config.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                }`}>
                  {alert.config.enabled ? '활성' : '비활성'}
                </span>
                <span className="text-sm font-medium text-slate-700 truncate">{alert.config.email}</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {scheduleLabel(alert.config.schedule, alert.config.hours)}
                {alert.state.last_sent && ` · 최근 발송: ${alert.state.last_sent}`}
              </p>
              {alert.config.rules.map((rule, i) => (
                <div key={i} className="mt-2 flex flex-wrap gap-1">
                  {rule.keywords.slice(0, 8).map((kw) => (
                    <span key={kw} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{kw}</span>
                  ))}
                  {rule.keywords.length > 8 && (
                    <span className="text-[11px] text-slate-400">+{rule.keywords.length - 8}</span>
                  )}
                  {rule.regions.length > 0 && (
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] text-blue-600">
                      {rule.regions.join(', ')}
                    </span>
                  )}
                </div>
              ))}
              <p className="mt-1 text-[10px] text-slate-400 font-mono">{alert.session_id}</p>
            </div>
            <div className="flex shrink-0 gap-1">
              <button
                type="button"
                onClick={() => void handleSendNow(alert.session_id)}
                disabled={sendingId === alert.session_id || !alert.config.enabled}
                className="rounded-lg p-2 text-blue-500 hover:bg-blue-50 disabled:opacity-30"
                title="즉시 발송"
              >
                {sendingId === alert.session_id ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
                ) : (
                  <Send size={16} />
                )}
              </button>
              <button
                type="button"
                onClick={() => void handleDelete(alert.session_id)}
                className="rounded-lg p-2 text-red-400 hover:bg-red-50 hover:text-red-600"
                title="삭제"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ── Shared UI ──

const SummaryCard: React.FC<{
  label: string;
  value: string;
  sub?: string;
  icon: React.FC<{ size?: number; className?: string }>;
  color: string;
}> = ({ label, value, sub, icon: Icon, color }) => {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    purple: 'bg-purple-50 text-purple-600',
    red: 'bg-red-50 text-red-600',
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <div className={`rounded-lg p-1.5 ${colorMap[color] || 'bg-slate-50 text-slate-500'}`}>
          <Icon size={16} />
        </div>
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <p className="mt-2 text-2xl font-bold tabular-nums text-slate-800">{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-slate-400">{sub}</p>}
    </div>
  );
};

const StatCard: React.FC<{ label: string; value: number; icon: React.FC<{ size?: number; className?: string }>; color: string }> = ({ label, value, icon: Icon, color }) => {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    indigo: 'bg-indigo-50 text-indigo-600',
    purple: 'bg-purple-50 text-purple-600',
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2">
        <div className={`rounded-lg p-1.5 ${colorMap[color] || 'bg-slate-50 text-slate-500'}`}>
          <Icon size={16} />
        </div>
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <p className="mt-2 text-2xl font-bold tabular-nums text-slate-800">{value.toLocaleString()}</p>
    </div>
  );
};

const LoadingSpinner: React.FC = () => (
  <div className="flex items-center justify-center p-12">
    <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
  </div>
);

const ErrorCard: React.FC<{ message: string; onRetry: () => void }> = ({ message, onRetry }) => (
  <div className="flex flex-col items-center gap-3 p-12 text-center">
    <p className="text-sm text-red-500">{message}</p>
    <button type="button" onClick={onRetry} className="rounded-lg bg-primary-600 px-4 py-2 text-sm text-white hover:bg-primary-700">
      다시 시도
    </button>
  </div>
);

function formatRelativeTime(iso: string): string {
  if (!iso) return '-';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '방금 전';
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

export default AdminPage;
