import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  TrendingUp, Search, CalendarClock, BarChart3, Wallet, ClipboardList,
  Clock, ChevronDown, ChevronUp, MapPin, FileText, Phone, Building2,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  getPopularAgencies, getOrgForecast, getCompanyProfile,
  type ForecastOrgData, type OrderPlan,
} from '../../services/kiraApiService';
import type { CompanyProfile } from '../../types';
import EmptyState from '../shared/EmptyState';
import { pageTransition } from '../../utils/animations';

// ── 유틸 ──

const RECENT_KEY = 'forecast_recent_orgs';
const MAX_RECENT = 5;

function getRecentOrgs(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); }
  catch { return []; }
}
function addRecentOrg(org: string) {
  const list = getRecentOrgs().filter(o => o !== org);
  list.unshift(org);
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, MAX_RECENT)));
}

function formatPrice(value?: string | number): string {
  const num = typeof value === 'number'
    ? value
    : parseInt(String(value ?? '').replace(/[^0-9]/g, ''));
  if (!num || isNaN(num) || num === 0) return '-';
  if (num >= 1_0000_0000) return `${(num / 1_0000_0000).toFixed(1)}억`;
  if (num >= 10000) return `${Math.round(num / 10000).toLocaleString()}만`;
  return `${num.toLocaleString()}원`;
}

function getDdayBadge(deadlineAt?: string | null): { text: string; cls: string } {
  if (!deadlineAt) return { text: '-', cls: 'bg-slate-100 text-slate-500' };
  const diff = Math.ceil((new Date(deadlineAt).getTime() - Date.now()) / 86400000);
  if (diff < 0) return { text: '마감', cls: 'bg-slate-100 text-slate-500' };
  if (diff <= 7) return { text: `D-${diff}`, cls: 'bg-red-50 text-red-700' };
  if (diff <= 14) return { text: `D-${diff}`, cls: 'bg-amber-50 text-amber-700' };
  return { text: `D-${diff}`, cls: 'bg-emerald-50 text-emerald-700' };
}

function amtTickFormatter(v: number): string {
  if (v >= 1_0000_0000) return `${(v / 1_0000_0000).toFixed(0)}억`;
  if (v >= 10000) return `${Math.round(v / 10000)}만`;
  return String(v);
}

// ── 인사이트 카드 계산 ──

function computeInsights(data: ForecastOrgData) {
  const entries = Object.entries(data.monthlyPattern).sort(([a], [b]) => a.localeCompare(b));

  // 집중 발주 시기
  const topMonths = [...entries]
    .sort(([, a], [, b]) => b.count - a.count)
    .slice(0, 2)
    .map(([m]) => `${parseInt(m.slice(5))}월`);

  // 발주 추세: 최근 3개월 vs 이전 3개월
  const recent3 = entries.slice(-3).reduce((s, [, v]) => s + v.count, 0);
  const prev3 = entries.slice(-6, -3).reduce((s, [, v]) => s + v.count, 0);
  const trendPct = prev3 > 0 ? Math.round(((recent3 - prev3) / prev3) * 100) : null;

  // 평균 공고 규모
  const totalAmt = entries.reduce((s, [, v]) => s + v.totalAmt, 0);
  const avgAmt = data.total > 0 ? Math.round(totalAmt / data.total) : null;

  // 주요 분야
  const catEntries = Object.entries(data.categoryBreakdown || {}).sort(([, a], [, b]) => b - a);
  const catTotal = catEntries.reduce((s, [, c]) => s + c, 0);
  const topCategory = catEntries.length > 0
    ? { name: catEntries[0][0], pct: catTotal > 0 ? Math.round((catEntries[0][1] / catTotal) * 100) : 0 }
    : null;

  return { topMonths, trendPct, avgAmt, topCategory, catEntries, catTotal };
}

// ── 컴포넌트 ──

const ForecastPage: React.FC = () => {
  const navigate = useNavigate();
  const [agencies, setAgencies] = useState<string[]>([]);
  const [recentOrgs, setRecentOrgs] = useState<string[]>(getRecentOrgs());
  const [searchInput, setSearchInput] = useState('');
  const [selectedOrg, setSelectedOrg] = useState<string | null>(null);
  const [data, setData] = useState<ForecastOrgData | null>(null);
  const [loading, setLoading] = useState(false);
  const [chartReady, setChartReady] = useState(false);
  const [chartTab, setChartTab] = useState<'count' | 'amount'>('count');
  const [companyProfile, setCompanyProfile] = useState<CompanyProfile | null>(null);

  useEffect(() => {
    getPopularAgencies().then(r => setAgencies(r.agencies)).catch(() => {});
    getCompanyProfile().then(p => setCompanyProfile(p)).catch(() => {});
    const timer = setTimeout(() => setChartReady(true), 300);
    return () => clearTimeout(timer);
  }, []);

  const handleSearch = useCallback(async (orgName: string) => {
    setSelectedOrg(orgName);
    setSearchInput(orgName);
    setLoading(true);
    setData(null);
    try {
      const result = await getOrgForecast(orgName);
      setData(result);
      addRecentOrg(orgName);
      setRecentOrgs(getRecentOrgs());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // 자동완성: 인기 기관 + 최근 검색에서 필터
  const suggestions = useMemo(() => {
    const q = searchInput.trim();
    if (!q) return [];
    const all = [...new Set([...recentOrgs, ...agencies])];
    return all.filter(a => a.includes(q) && a !== selectedOrg).slice(0, 6);
  }, [searchInput, recentOrgs, agencies, selectedOrg]);

  const chartData = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.monthlyPattern)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, val]) => ({
        month,
        label: `${parseInt(month.slice(5))}월`,
        count: val.count,
        amount: val.totalAmt,
      }));
  }, [data]);

  const insights = useMemo(() => data ? computeInsights(data) : null, [data]);

  const hasResults = !loading && data && data.total > 0;
  const hasOrderPlans = data?.orderPlans && data.orderPlans.length > 0;
  const hasAmountData = chartData.some(d => d.amount > 0);

  return (
    <motion.div
      className="flex-1 overflow-y-auto p-6 lg:p-8"
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="max-w-5xl mx-auto">
        {/* 헤더 */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">발주예측</h1>
          <p className="mt-1 text-sm text-slate-500">
            관심 기관의 과거 발주 패턴을 분석하여 향후 입찰 기회를 미리 파악하세요.
          </p>
        </div>

        {/* 검색바 */}
        <div className="relative mb-2">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && searchInput.trim()) handleSearch(searchInput.trim()); }}
                placeholder="기관명 검색 (예: 한국도로공사)"
                className="w-full rounded-lg border border-slate-300 pl-10 pr-4 py-2.5 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none"
              />
            </div>
            <button
              type="button"
              onClick={() => searchInput.trim() && handleSearch(searchInput.trim())}
              className="rounded-lg bg-kira-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-kira-700 transition-colors"
            >
              검색
            </button>
          </div>

          {/* 자동완성 드롭다운 */}
          {suggestions.length > 0 && !loading && (
            <div className="absolute z-10 top-full left-0 right-16 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden">
              {suggestions.map(s => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleSearch(s)}
                  className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 최근 검색 */}
        {recentOrgs.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="text-xs text-slate-400">최근:</span>
            {recentOrgs.map(o => (
              <button
                key={o}
                type="button"
                onClick={() => handleSearch(o)}
                className={`rounded-full px-3 py-1 text-xs font-medium border border-dashed transition-colors ${
                  selectedOrg === o
                    ? 'border-kira-500 bg-kira-50 text-kira-700'
                    : 'border-slate-300 text-slate-500 hover:border-kira-400 hover:bg-kira-50'
                }`}
              >
                {o}
              </button>
            ))}
          </div>
        )}

        {/* 인기 기관 칩 */}
        <div className="flex flex-wrap gap-2 mb-6">
          {agencies.slice(0, 12).map(a => (
            <button
              key={a}
              type="button"
              onClick={() => handleSearch(a)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium border transition-colors ${
                selectedOrg === a
                  ? 'border-kira-600 bg-kira-600 text-white'
                  : 'border-slate-300 text-slate-600 hover:border-kira-400 hover:bg-kira-50'
              }`}
            >
              {a}
            </button>
          ))}
        </div>

        {/* 맞춤 추천 */}
        {companyProfile?.companyName && (companyProfile.regions?.length > 0 || companyProfile.specializations?.length > 0) && (
          <div className="rounded-xl border border-kira-200 bg-kira-50/50 p-4 mb-6">
            <h3 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-1.5">
              <Building2 size={15} className="text-kira-600" />
              {companyProfile.companyName} 맞춤 추천
            </h3>
            <p className="text-xs text-slate-500 mb-3">
              {[
                companyProfile.businessType && `업종: ${companyProfile.businessType}`,
                companyProfile.regions?.length > 0 && `지역: ${companyProfile.regions.join(', ')}`,
                companyProfile.specializations?.length > 0 && `전문: ${companyProfile.specializations.slice(0, 3).join(', ')}`,
              ].filter(Boolean).join(' · ')}
            </p>
            <div className="flex flex-wrap gap-2">
              {companyProfile.keyExperience?.slice(0, 5).map(exp => (
                <button
                  key={exp}
                  type="button"
                  onClick={() => handleSearch(exp)}
                  className="rounded-full px-3 py-1 text-xs font-medium border border-kira-300 text-kira-700 bg-white hover:bg-kira-100 transition-colors"
                >
                  {exp}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 로딩 */}
        {loading && (
          <div className="flex justify-center py-16">
            <div className="flex gap-1">
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
            </div>
          </div>
        )}

        {/* 결과 영역 */}
        {hasResults && insights && (
          <div className="space-y-5">

            {/* 인사이트 카드 4개 */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <InsightCard
                icon={<CalendarClock size={18} />}
                iconBg="bg-blue-50 text-blue-600"
                title="집중 발주 시기"
                value={insights.topMonths.length > 0 ? insights.topMonths.join(', ') : null}
                sub="연간 최다 발주 월"
              />
              <InsightCard
                icon={<TrendingUp size={18} />}
                iconBg="bg-emerald-50 text-emerald-600"
                title="발주 추세"
                value={insights.trendPct !== null ? `${insights.trendPct > 0 ? '+' : ''}${insights.trendPct}%` : null}
                sub="최근 3개월 vs 이전 3개월"
                valueColor={insights.trendPct !== null ? (insights.trendPct >= 0 ? 'text-emerald-600' : 'text-red-600') : undefined}
              />
              <InsightCard
                icon={<Wallet size={18} />}
                iconBg="bg-violet-50 text-violet-600"
                title={hasAmountData ? "평균 공고 규모" : "총 공고 수"}
                value={hasAmountData && insights.avgAmt ? formatPrice(insights.avgAmt) : `${data!.total}건`}
                sub={hasAmountData ? "추정가격 기준" : "최근 12개월"}
              />
              <InsightCard
                icon={<ClipboardList size={18} />}
                iconBg="bg-amber-50 text-amber-600"
                title="주요 분야"
                value={insights.topCategory ? `${insights.topCategory.name} ${insights.topCategory.pct}%` : null}
                sub={insights.catEntries.length > 1 ? `외 ${insights.catEntries.length - 1}개 분야` : ''}
              />
            </div>

            {/* 발주예정 사업 (사전공개) */}
            {hasOrderPlans && (
              <OrderPlansSection plans={data!.orderPlans} companyProfile={companyProfile} />
            )}

            {/* 차트 */}
            {chartData.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-slate-900">월별 발주 현황</h2>
                  <div className="flex rounded-lg border border-slate-200 overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setChartTab('count')}
                      className={`px-3 py-1 text-xs font-medium transition-colors ${
                        chartTab === 'count' ? 'bg-kira-600 text-white' : 'text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      공고 건수
                    </button>
                    <button
                      type="button"
                      onClick={() => hasAmountData && setChartTab('amount')}
                      disabled={!hasAmountData}
                      className={`px-3 py-1 text-xs font-medium transition-colors ${
                        chartTab === 'amount' ? 'bg-kira-600 text-white' : !hasAmountData ? 'text-slate-300 cursor-not-allowed' : 'text-slate-600 hover:bg-slate-50'
                      }`}
                      title={!hasAmountData ? '이 기관의 추정가격 데이터가 없습니다' : undefined}
                    >
                      추정 금액
                    </button>
                  </div>
                </div>
                <div style={{ width: '100%', minHeight: 250 }}>
                  {chartReady && (
                    <ResponsiveContainer width="100%" height={250} minWidth={100}>
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                        <YAxis
                          tick={{ fontSize: 12 }}
                          allowDecimals={false}
                          tickFormatter={chartTab === 'amount' ? amtTickFormatter : undefined}
                        />
                        <Tooltip
                          formatter={(value: number) =>
                            chartTab === 'amount' ? formatPrice(value) : `${value}건`
                          }
                          labelFormatter={(label: string) => label}
                        />
                        <Bar
                          dataKey={chartTab === 'count' ? 'count' : 'amount'}
                          fill={chartTab === 'count' ? '#2563eb' : '#7c3aed'}
                          radius={[4, 4, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            )}

            {/* 최근 공고 목록 */}
            {data!.recentBids.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="text-base font-semibold text-slate-900 mb-4">
                  최근 공고 ({data!.total}건)
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200">
                        <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">공고명</th>
                        <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">
                          {hasAmountData ? '추정가격' : '수요기관'}
                        </th>
                        <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">마감일</th>
                        <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">분류</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data!.recentBids.map(bid => {
                        const dday = getDdayBadge(bid.deadlineAt);
                        return (
                          <tr key={bid.id} className="border-b border-slate-100 hover:bg-slate-50">
                            <td className="py-2.5 px-2 max-w-xs truncate font-medium text-slate-800">
                              {bid.url ? (
                                <a href={bid.url} target="_blank" rel="noreferrer" className="hover:text-kira-600 hover:underline">
                                  {bid.title}
                                </a>
                              ) : bid.title}
                            </td>
                            <td className="py-2.5 px-2 text-slate-600 whitespace-nowrap max-w-[140px] truncate">
                              {hasAmountData ? formatPrice(bid.estimatedPrice) : (bid.demandOrg || bid.issuingOrg || '-')}
                            </td>
                            <td className="py-2.5 px-2 whitespace-nowrap">
                              <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${dday.cls}`}>
                                {dday.text}
                              </span>
                            </td>
                            <td className="py-2.5 px-2 text-slate-500">{bid.category || '-'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 0건 Empty State */}
        {!loading && data && data.total === 0 && !hasOrderPlans && (
          <div className="text-center py-16 rounded-xl border border-slate-200 bg-white">
            <Search size={32} className="text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-600 mb-2">
              최근 12개월 내 공고 데이터가 없습니다
            </h3>
            <p className="text-sm text-slate-400 mb-6">
              이 기관의 새로운 공고가 등록되면 알림을 받아보세요.
            </p>
            <button
              type="button"
              onClick={() => navigate('/settings/alerts')}
              className="px-4 py-2 bg-kira-600 text-white rounded-lg text-sm hover:bg-kira-700 transition-colors"
            >
              이 기관 알림 설정하기
            </button>
          </div>
        )}

        {/* 초기 Empty State */}
        {!loading && !data && (
          <EmptyState
            icon={TrendingUp}
            title="기관을 검색해보세요"
            description="기관명을 검색하면 최근 12개월 발주 패턴, 금액 추이, 발주예정 사업을 한눈에 확인할 수 있어요."
          />
        )}
      </div>
    </motion.div>
  );
};


// ── 하위 컴포넌트 ──

function InsightCard({ icon, iconBg, title, value, sub, valueColor }: {
  icon: React.ReactNode;
  iconBg: string;
  title: string;
  value: string | null;
  sub: string;
  valueColor?: string;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <div className={`inline-flex p-2 rounded-lg mb-3 ${iconBg}`}>{icon}</div>
      <p className="text-xs font-medium text-slate-500 tracking-wider mb-1">{title}</p>
      <p className={`text-xl font-bold ${valueColor || 'text-slate-900'}`}>
        {value || <span className="text-slate-300 text-sm font-normal">데이터 수집 중</span>}
      </p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  );
}

function getRelevanceBadge(plan: OrderPlan, profile: CompanyProfile | null): { text: string; cls: string } | null {
  if (!profile) return null;
  let score = 0;
  // 지역 매칭
  if (profile.regions?.some(r => plan.cnstwkRgnNm?.includes(r) || plan.jrsdctnDivNm?.includes(r))) score++;
  // 전문분야 매칭
  if (profile.specializations?.some(s => plan.bizNm?.includes(s) || plan.category?.includes(s))) score++;
  // 경험 매칭
  if (profile.keyExperience?.some(k => plan.bizNm?.includes(k) || plan.usgCntnts?.includes(k))) score++;

  if (score >= 2) return { text: '적합도 높음', cls: 'bg-emerald-100 text-emerald-700' };
  if (score >= 1) return { text: '적합도 보통', cls: 'bg-amber-100 text-amber-700' };
  return null;
}

function OrderPlansSection({ plans, companyProfile }: { plans: OrderPlan[]; companyProfile?: CompanyProfile | null }) {
  const [filter, setFilter] = useState<'all' | 'unannounced' | 'announced'>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const unannounced = plans.filter(p => p.ntcePblancYn !== 'Y');
  const announced = plans.filter(p => p.ntcePblancYn === 'Y');
  const filtered = filter === 'all' ? plans : filter === 'unannounced' ? unannounced : announced;

  const totalBudget = plans.reduce((s, p) => s + (p.sumOrderAmt || p.orderAmt || 0), 0);

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-5">
      {/* 헤더 */}
      <div className="flex items-center gap-2 mb-1">
        <Clock size={18} className="text-amber-600" />
        <h2 className="text-base font-semibold text-slate-900">
          발주예정 사업 ({plans.length}건)
        </h2>
        {unannounced.length > 0 && (
          <span className="text-xs text-amber-700 bg-amber-200/70 px-2 py-0.5 rounded-full font-medium">
            미공고 {unannounced.length}건
          </span>
        )}
      </div>

      {/* 요약 */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-amber-700/80 mb-3">
        <span>총 예산 {totalBudget > 0 ? formatPrice(totalBudget) : '-'}</span>
        <span>·</span>
        <span>미공고 {unannounced.length}건 / 공고완료 {announced.length}건</span>
      </div>

      {/* 필터 탭 */}
      <div className="flex gap-1 mb-4">
        {([
          ['all', `전체 (${plans.length})`],
          ['unannounced', `미공고 (${unannounced.length})`],
          ['announced', `공고완료 (${announced.length})`],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setFilter(key)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filter === key
                ? 'bg-amber-600 text-white'
                : 'bg-amber-100/60 text-amber-700 hover:bg-amber-200/60'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 테이블 */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-amber-200/60">
              <th className="text-left py-2 px-2 text-xs font-medium text-slate-500 w-8" />
              <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">사업명</th>
              <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">예산</th>
              <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">발주 시기</th>
              <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">조달방식</th>
              <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">상태</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(plan => {
              const isExpanded = expandedId === plan.id;
              const monthLabel = plan.orderMnth
                ? `${plan.orderYear}년 ${parseInt(plan.orderMnth)}월`
                : `${plan.orderYear}년`;
              const isUnannounced = plan.ntcePblancYn !== 'Y';

              return (
                <React.Fragment key={plan.id}>
                  <tr
                    className="border-b border-amber-100/60 hover:bg-amber-100/30 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : plan.id)}
                  >
                    <td className="py-2.5 px-2 text-slate-400">
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </td>
                    <td className="py-2.5 px-2 max-w-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-900 truncate">{plan.bizNm || '-'}</span>
                        {(() => {
                          const badge = getRelevanceBadge(plan, companyProfile ?? null);
                          return badge ? (
                            <span className={`shrink-0 inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${badge.cls}`}>
                              {badge.text}
                            </span>
                          ) : null;
                        })()}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        {plan.category && (
                          <span className="text-xs text-slate-400">{plan.category}</span>
                        )}
                        {plan.bsnsTyNm && (
                          <span className="text-xs text-slate-400">· {plan.bsnsTyNm}</span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-2 text-slate-700 whitespace-nowrap">
                      {formatPrice(plan.sumOrderAmt || plan.orderAmt)}
                    </td>
                    <td className="py-2.5 px-2 text-slate-600 whitespace-nowrap">
                      {monthLabel}
                    </td>
                    <td className="py-2.5 px-2 text-slate-500 whitespace-nowrap">
                      {plan.cntrctMthdNm || plan.prcrmntMethd || '-'}
                    </td>
                    <td className="py-2.5 px-2 whitespace-nowrap">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        isUnannounced
                          ? 'bg-amber-200/70 text-amber-800'
                          : 'bg-emerald-100 text-emerald-700'
                      }`}>
                        {isUnannounced ? '미공고' : '공고완료'}
                      </span>
                    </td>
                  </tr>

                  {/* 확장 상세 */}
                  <AnimatePresence>
                    {isExpanded && (
                      <tr>
                        <td colSpan={6} className="p-0">
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="bg-white/60 border-b border-amber-100/60 px-4 py-3 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-xs">
                              {plan.orderInsttNm && (
                                <div className="flex items-start gap-2">
                                  <Building2 size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">발주기관</span>
                                    <p className="text-slate-700">{plan.orderInsttNm}</p>
                                  </div>
                                </div>
                              )}
                              {plan.deptNm && (
                                <div className="flex items-start gap-2">
                                  <Building2 size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">부서</span>
                                    <p className="text-slate-700">{plan.deptNm}</p>
                                  </div>
                                </div>
                              )}
                              {(plan.cnstwkRgnNm || plan.jrsdctnDivNm) && (
                                <div className="flex items-start gap-2">
                                  <MapPin size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">지역</span>
                                    <p className="text-slate-700">
                                      {[plan.cnstwkRgnNm, plan.jrsdctnDivNm].filter(Boolean).join(' / ')}
                                    </p>
                                  </div>
                                </div>
                              )}
                              {plan.ofclNm && (
                                <div className="flex items-start gap-2">
                                  <Phone size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">담당자</span>
                                    <p className="text-slate-700">
                                      {plan.ofclNm}{plan.telNo ? ` (${plan.telNo})` : ''}
                                    </p>
                                  </div>
                                </div>
                              )}
                              {plan.prdctClsfcNoNm && (
                                <div className="flex items-start gap-2">
                                  <ClipboardList size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">품명분류</span>
                                    <p className="text-slate-700">{plan.prdctClsfcNoNm}</p>
                                  </div>
                                </div>
                              )}
                              {plan.totlmngInsttNm && (
                                <div className="flex items-start gap-2">
                                  <Building2 size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">총괄기관</span>
                                    <p className="text-slate-700">{plan.totlmngInsttNm}</p>
                                  </div>
                                </div>
                              )}
                              {plan.usgCntnts && (
                                <div className="flex items-start gap-2 sm:col-span-2">
                                  <FileText size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">용도</span>
                                    <p className="text-slate-700">{plan.usgCntnts}</p>
                                  </div>
                                </div>
                              )}
                              {plan.specCntnts && (
                                <div className="flex items-start gap-2 sm:col-span-2">
                                  <FileText size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">사양</span>
                                    <p className="text-slate-700">{plan.specCntnts}</p>
                                  </div>
                                </div>
                              )}
                              {plan.rmrkCntnts && (
                                <div className="flex items-start gap-2 sm:col-span-2">
                                  <FileText size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">비고</span>
                                    <p className="text-slate-700">{plan.rmrkCntnts}</p>
                                  </div>
                                </div>
                              )}
                              {plan.bidNtceNoList && (
                                <div className="flex items-start gap-2 sm:col-span-2">
                                  <FileText size={13} className="text-slate-400 mt-0.5 shrink-0" />
                                  <div>
                                    <span className="text-slate-400">연관 공고번호</span>
                                    <p className="text-slate-700">{plan.bidNtceNoList}</p>
                                  </div>
                                </div>
                              )}
                            </div>
                          </motion.div>
                        </td>
                      </tr>
                    )}
                  </AnimatePresence>
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-sm text-amber-600/70 py-4">
          {filter === 'unannounced' ? '미공고 발주계획이 없습니다.' : '공고완료된 발주계획이 없습니다.'}
        </p>
      )}
    </div>
  );
}

export default ForecastPage;
