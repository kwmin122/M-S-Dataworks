import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FileSearch, Clock, CheckCircle2, BarChart3, Bell, BellOff, Settings } from 'lucide-react';
import { useChatContext } from '../../context/ChatContext';
import SummaryCard from './SummaryCard';
import { getDashboardSummary, getAlertConfig, saveAlertConfig, type DashboardSummary, type AlertConfig } from '../../services/kiraApiService';
import { staggerContainer, pageTransition } from '../../utils/animations';

const DashboardPage: React.FC = () => {
  const { state } = useChatContext();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [alertConfig, setAlertConfig] = useState<AlertConfig | null>(null);
  const [alertToggling, setAlertToggling] = useState(false);
  const [loading, setLoading] = useState(true);

  // Find session from active conversation
  const activeConv = state.conversations.find(c => c.id === state.activeConversationId);
  const sessionId = activeConv?.sessionId;

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    Promise.all([
      getDashboardSummary(sessionId).catch(() => null),
      getAlertConfig(sessionId).catch(() => null),
    ]).then(([dashData, alertData]) => {
      if (cancelled) return;
      if (dashData) setSummary(dashData);
      if (alertData) setAlertConfig(alertData);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionId]);

  const handleToggleAlert = async () => {
    if (!sessionId || !alertConfig) return;
    setAlertToggling(true);
    try {
      const updated = { ...alertConfig, enabled: !alertConfig.enabled };
      await saveAlertConfig(sessionId, updated);
      setAlertConfig(updated);
    } catch { /* silently ignore */ }
    finally { setAlertToggling(false); }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex gap-1">
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
        </div>
      </div>
    );
  }

  const displaySummary: DashboardSummary = summary || {
    newMatches: 0,
    deadlineSoon: 0,
    goCount: 0,
    totalAnalyzed: 0,
    recentSearches: [],
    smartFitTop5: [],
  };

  return (
    <motion.div
      className="flex-1 overflow-y-auto p-6 lg:p-8"
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">대시보드</h1>

        {/* Summary Cards */}
        <motion.div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8"
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
        >
          <SummaryCard
            icon={FileSearch}
            label="새 맞춤 공고"
            value={displaySummary.newMatches}
            color="text-kira-600"
            bgColor="bg-kira-50"
            actionLabel="검색하기"
            onAction={() => navigate('/chat')}
          />
          <SummaryCard
            icon={Clock}
            label="마감 임박"
            value={displaySummary.deadlineSoon}
            color="text-amber-600"
            bgColor="bg-amber-50"
          />
          <SummaryCard
            icon={CheckCircle2}
            label="GO 판정"
            value={displaySummary.goCount}
            color="text-green-600"
            bgColor="bg-green-50"
          />
          <SummaryCard
            icon={BarChart3}
            label="분석 완료"
            value={displaySummary.totalAnalyzed}
            color="text-purple-600"
            bgColor="bg-purple-50"
          />
        </motion.div>

        {/* Smart Fit placeholder */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-2">Smart Fit Top 5</h2>
          <p className="text-sm text-slate-500">회사 문서를 등록하면 가장 잘 맞는 공고를 자동으로 추천해드려요.</p>
        </div>

        {/* Alert Management */}
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-kira-600" />
              <h2 className="text-lg font-semibold text-slate-900">공고 알림</h2>
            </div>
            <button
              type="button"
              onClick={() => navigate('/settings/alerts')}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-kira-600 transition-colors"
            >
              <Settings size={14} />
              설정
            </button>
          </div>
          {alertConfig && alertConfig.rules.length > 0 ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-700">
                    {alertConfig.enabled ? '알림 활성화됨' : '알림 일시정지됨'}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {alertConfig.rules.length}개 규칙 · {alertConfig.email || '이메일 미설정'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleToggleAlert}
                  disabled={alertToggling}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    alertConfig.enabled
                      ? 'bg-red-50 text-red-600 hover:bg-red-100 border border-red-200'
                      : 'bg-kira-50 text-kira-600 hover:bg-kira-100 border border-kira-200'
                  } disabled:opacity-50`}
                >
                  {alertConfig.enabled ? (
                    <><BellOff size={14} /> 알림 멈추기</>
                  ) : (
                    <><Bell size={14} /> 알림 다시 시작</>
                  )}
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {alertConfig.rules.flatMap(r => r.keywords).slice(0, 10).map((kw, i) => (
                  <span key={i} className="rounded-full bg-kira-50 px-2.5 py-0.5 text-xs text-kira-700 border border-kira-200">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-sm text-slate-500 mb-2">아직 설정된 알림이 없어요</p>
              <button
                type="button"
                onClick={() => navigate('/settings/alerts')}
                className="rounded-lg bg-kira-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-kira-700 transition-colors"
              >
                알림 설정하기
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default DashboardPage;
