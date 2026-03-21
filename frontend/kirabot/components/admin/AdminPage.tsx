import React, { useState, useEffect, useCallback } from 'react';
import { BarChart3, Bell, Trash2, Send, RefreshCw, Users, MessageSquare, FileSearch, Activity } from 'lucide-react';
import {
  getAdminUsage,
  getAdminAlerts,
  deleteAdminAlert,
  sendAdminAlertNow,
  type AdminUsageResponse,
  type AdminAlertItem,
} from '../../services/kiraApiService';
import ObservabilityDashboard from './ObservabilityDashboard';

type Tab = 'usage' | 'alerts' | 'observability';

const AdminPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('usage');

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* Header */}
      <div className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-lg font-bold text-slate-800">관리자</h1>
        <div className="mt-3 flex gap-1">
          {([
            { key: 'usage' as Tab, label: '사용량', icon: BarChart3 },
            { key: 'observability' as Tab, label: '운영 메트릭', icon: Activity },
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
        {tab === 'usage' ? <UsagePanel /> : tab === 'observability' ? <ObservabilityDashboard /> : <AlertsPanel />}
      </div>
    </div>
  );
};

// ── Usage Dashboard ──

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
