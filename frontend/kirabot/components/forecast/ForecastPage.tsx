import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, Search, AlertTriangle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getPopularAgencies, getOrgForecast, type ForecastOrgData } from '../../services/kiraApiService';
import EmptyState from '../shared/EmptyState';
import { pageTransition } from '../../utils/animations';

const ForecastPage: React.FC = () => {
  const [agencies, setAgencies] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState('');
  const [selectedOrg, setSelectedOrg] = useState<string | null>(null);
  const [data, setData] = useState<ForecastOrgData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getPopularAgencies().then(r => setAgencies(r.agencies)).catch(() => {});
  }, []);

  const handleSearch = async (orgName: string) => {
    setSelectedOrg(orgName);
    setLoading(true);
    try {
      const result = await getOrgForecast(orgName);
      setData(result);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const chartData = data
    ? Object.entries(data.monthlyPattern)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([month, val]) => ({ month: month.slice(5), count: val.count }))
    : [];

  return (
    <motion.div
      className="flex-1 overflow-y-auto p-6 lg:p-8"
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">발주예측</h1>

        {/* Search bar */}
        <div className="flex gap-2 mb-4">
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

        {/* Popular agencies chips */}
        <div className="flex flex-wrap gap-2 mb-6">
          {agencies.slice(0, 12).map(a => (
            <button
              key={a}
              type="button"
              onClick={() => { setSearchInput(a); handleSearch(a); }}
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

        {/* Loading */}
        {loading && (
          <div className="flex justify-center py-12">
            <div className="flex gap-1">
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
            </div>
          </div>
        )}

        {/* Results */}
        {!loading && data && (
          <div className="space-y-4">
            {/* Chart */}
            {chartData.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="text-base font-semibold text-slate-900 mb-4">월별 공고 건수</h2>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* AI Insight */}
            <div className="rounded-xl border border-ai-200 bg-ai-50 p-5">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={16} className="text-ai-600" />
                <span className="text-xs font-medium text-ai-700 bg-ai-200 px-2 py-0.5 rounded-full">참고용</span>
              </div>
              <p className="text-sm text-slate-700">{data.aiInsight}</p>
            </div>

            {/* Recent bids table */}
            {data.recentBids.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="text-base font-semibold text-slate-900 mb-4">최근 공고 ({data.total}건)</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200">
                        <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">공고명</th>
                        <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">마감일</th>
                        <th className="text-left py-2 px-2 text-xs font-medium text-slate-500">분류</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recentBids.map(bid => (
                        <tr key={bid.id} className="border-b border-slate-100 hover:bg-slate-50">
                          <td className="py-2 px-2 max-w-xs truncate">{bid.title}</td>
                          <td className="py-2 px-2 text-slate-500 whitespace-nowrap">{bid.deadlineAt?.slice(0, 10) || '-'}</td>
                          <td className="py-2 px-2 text-slate-500">{bid.category || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {!loading && !data && (
          <EmptyState
            icon={TrendingUp}
            title="기관을 검색해보세요"
            description="기관명을 검색하면 과거 입찰 패턴과 AI 인사이트를 확인할 수 있어요."
          />
        )}
      </div>
    </motion.div>
  );
};

export default ForecastPage;
