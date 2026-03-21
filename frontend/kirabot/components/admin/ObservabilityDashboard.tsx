import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Activity, CheckCircle2, XCircle, Clock, DollarSign, AlertTriangle, Timer } from 'lucide-react';
import {
  getAdminMetrics,
  type AdminMetrics,
  type EventTypeMetrics,
} from '../../services/studioApi';

type PeriodOption = 7 | 14 | 30 | 90;

const PERIOD_OPTIONS: { value: PeriodOption; label: string }[] = [
  { value: 7, label: '7일' },
  { value: 14, label: '14일' },
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

const ObservabilityDashboard: React.FC = () => {
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

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 p-12 text-center">
        <p className="text-sm text-red-500">{error}</p>
        <button type="button" onClick={() => void load()} className="rounded-lg bg-primary-600 px-4 py-2 text-sm text-white hover:bg-primary-700">
          다시 시도
        </button>
      </div>
    );
  }

  if (!data) return null;

  const { summary, by_event_type, by_doc_type, cost, quality, daily_trend } = data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-slate-500" />
          <span className="text-sm font-semibold text-slate-700">운영 메트릭</span>
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

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <SummaryCard
          label="총 이벤트"
          value={summary.total_events.toLocaleString()}
          icon={Activity}
          color="blue"
        />
        <SummaryCard
          label="성공률"
          value={`${(summary.success_rate * 100).toFixed(1)}%`}
          icon={CheckCircle2}
          color="emerald"
        />
        <SummaryCard
          label="실패/타임아웃"
          value={`${summary.failure_count} / ${summary.timeout_count}`}
          icon={XCircle}
          color="red"
        />
        <SummaryCard
          label="총 비용"
          value={`$${cost.total_usd.toFixed(2)}`}
          icon={DollarSign}
          color="amber"
        />
      </div>

      {/* Event type breakdown */}
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-4 py-3">
          <span className="text-sm font-semibold text-slate-700">이벤트 유형별</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                <th className="px-4 py-2">유형</th>
                <th className="px-4 py-2 text-right">횟수</th>
                <th className="px-4 py-2 text-right">성공</th>
                <th className="px-4 py-2 text-right">실패</th>
                <th className="px-4 py-2 text-right">평균 소요(ms)</th>
                <th className="px-4 py-2 w-40">비율</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(by_event_type).length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                    이벤트 데이터가 없습니다.
                  </td>
                </tr>
              ) : (
                Object.entries(by_event_type)
                  .sort(([, a], [, b]) => b.count - a.count)
                  .map(([type, metrics]) => (
                    <EventTypeRow
                      key={type}
                      type={type}
                      metrics={metrics}
                      maxCount={Math.max(...Object.values(by_event_type).map((m) => m.count))}
                    />
                  ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Doc type breakdown */}
      {Object.keys(by_doc_type).length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3">
            <span className="text-sm font-semibold text-slate-700">문서 유형별</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                  <th className="px-4 py-2">문서</th>
                  <th className="px-4 py-2 text-right">횟수</th>
                  <th className="px-4 py-2 text-right">평균 소요(ms)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(by_doc_type)
                  .sort(([, a], [, b]) => b.count - a.count)
                  .map(([docType, m]) => (
                    <tr key={docType} className="border-b border-slate-50 last:border-b-0 hover:bg-slate-25">
                      <td className="px-4 py-2 font-medium text-slate-700">
                        {DOC_TYPE_LABELS[docType] || docType}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                        {m.count.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                        {m.avg_duration_ms.toLocaleString()}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Performance targets */}
      {Object.keys(by_doc_type).length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3 flex items-center gap-2">
            <Timer size={15} className="text-slate-500" />
            <span className="text-sm font-semibold text-slate-700">성능 (목표 대비)</span>
          </div>
          <div className="p-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
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

      {/* Cost breakdown */}
      {Object.keys(cost.by_model).length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3">
            <span className="text-sm font-semibold text-slate-700">모델별 비용</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                  <th className="px-4 py-2">모델</th>
                  <th className="px-4 py-2 text-right">토큰</th>
                  <th className="px-4 py-2 text-right">비용 (USD)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(cost.by_model)
                  .sort(([, a], [, b]) => b.cost_usd - a.cost_usd)
                  .map(([model, m]) => (
                    <tr key={model} className="border-b border-slate-50 last:border-b-0 hover:bg-slate-25">
                      <td className="px-4 py-2 font-medium text-slate-700 font-mono text-xs">{model}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                        {m.tokens.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                        ${m.cost_usd.toFixed(4)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Quality signals */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex items-center gap-2">
          <AlertTriangle size={15} className="text-amber-500" />
          <span className="text-sm font-semibold text-slate-700">품질 신호</span>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs font-medium text-slate-500">수동 오버라이드</p>
            <p className="mt-1 text-xl font-bold tabular-nums text-slate-800">{quality.override_count}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">저신뢰도 분류</p>
            <p className="mt-1 text-xl font-bold tabular-nums text-slate-800">{quality.low_confidence_count}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">평균 품질 점수</p>
            <p className="mt-1 text-xl font-bold tabular-nums text-slate-400">
              {quality.avg_quality_score !== null ? quality.avg_quality_score.toFixed(1) : '-'}
            </p>
          </div>
        </div>
      </div>

      {/* Daily trend */}
      {daily_trend.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="mb-4 flex items-center gap-2">
            <Clock size={15} className="text-slate-500" />
            <span className="text-sm font-semibold text-slate-700">일별 추이</span>
          </div>
          <DailyTrendChart data={daily_trend} />
          <div className="mt-3 flex items-center gap-4 text-[11px] text-slate-400">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-400" /> 성공
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-400" /> 실패
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

// --- Sub-components ---

const SummaryCard: React.FC<{
  label: string;
  value: string;
  icon: React.FC<{ size?: number; className?: string }>;
  color: string;
}> = ({ label, value, icon: Icon, color }) => {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    red: 'bg-red-50 text-red-600',
    amber: 'bg-amber-50 text-amber-600',
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2">
        <div className={`rounded-lg p-1.5 ${colorMap[color] || 'bg-slate-50 text-slate-500'}`}>
          <Icon size={16} />
        </div>
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <p className="mt-2 text-2xl font-bold tabular-nums text-slate-800">{value}</p>
    </div>
  );
};

const EventTypeRow: React.FC<{
  type: string;
  metrics: EventTypeMetrics;
  maxCount: number;
}> = ({ type, metrics, maxCount }) => {
  const pct = maxCount > 0 ? (metrics.count / maxCount) * 100 : 0;
  const successPct = metrics.count > 0 ? (metrics.success / metrics.count) * 100 : 0;
  return (
    <tr className="border-b border-slate-50 last:border-b-0 hover:bg-slate-25">
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
      <td className="px-4 py-2">
        <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
          <div
            className="h-full rounded-full bg-primary-400 transition-all"
            style={{ width: `${pct}%` }}
          >
            <div
              className="h-full rounded-full bg-emerald-400"
              style={{ width: `${successPct}%` }}
            />
          </div>
        </div>
      </td>
    </tr>
  );
};

const DailyTrendChart: React.FC<{
  data: Array<{ date: string; events: number; success: number; failure: number }>;
}> = ({ data }) => {
  const maxEvents = Math.max(...data.map((d) => d.events), 1);
  const chartHeight = 120;

  return (
    <div className="flex items-end gap-px" style={{ height: chartHeight }}>
      {data.map((d) => {
        const totalH = (d.events / maxEvents) * chartHeight;
        const failH = d.failure > 0 ? Math.max((d.failure / maxEvents) * chartHeight, 2) : 0;
        const successH = totalH - failH;
        const dateLabel = d.date.slice(5); // "03-20"
        return (
          <div
            key={d.date}
            className="group relative flex flex-1 flex-col justify-end"
            style={{ height: chartHeight }}
          >
            {/* Tooltip */}
            <div className="pointer-events-none absolute -top-8 left-1/2 z-10 hidden -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-[10px] text-white group-hover:block">
              {d.date}: {d.events} ({d.success}ok / {d.failure}fail)
            </div>
            {/* Bars */}
            <div className="flex flex-col">
              {failH > 0 && (
                <div
                  className="w-full rounded-t bg-red-400"
                  style={{ height: `${failH}px` }}
                />
              )}
              <div
                className={`w-full bg-emerald-400 ${failH > 0 ? '' : 'rounded-t'}`}
                style={{ height: `${Math.max(successH, 0)}px` }}
              />
            </div>
            {/* Date label — show every Nth depending on count */}
            {(data.length <= 14 || data.indexOf(d) % Math.ceil(data.length / 14) === 0) && (
              <span className="mt-1 block text-center text-[9px] text-slate-400 truncate">
                {dateLabel}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default ObservabilityDashboard;
