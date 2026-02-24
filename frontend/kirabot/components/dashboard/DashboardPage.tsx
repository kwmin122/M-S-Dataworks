import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FileSearch, Clock, CheckCircle2, BarChart3, FileText } from 'lucide-react';
import { useChatContext } from '../../context/ChatContext';
import SummaryCard from './SummaryCard';
import EmptyState from '../shared/EmptyState';
import { getDashboardSummary, type DashboardSummary } from '../../services/kiraApiService';
import { staggerContainer, pageTransition } from '../../utils/animations';

const DashboardPage: React.FC = () => {
  const { state } = useChatContext();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
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
    getDashboardSummary(sessionId)
      .then(data => { if (!cancelled) setSummary(data); })
      .catch(() => { /* silently ignore */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionId]);

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

  if (!sessionId || !summary) {
    return (
      <div className="flex-1">
        <EmptyState
          icon={FileText}
          title="아직 분석한 공고가 없어요"
          description="공고를 검색하고 분석하면 대시보드에 요약 정보가 표시됩니다."
          actionLabel="공고 검색 시작"
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
            value={summary.newMatches}
            color="text-kira-600"
            bgColor="bg-kira-50"
            actionLabel="검색하기"
            onAction={() => navigate('/chat')}
          />
          <SummaryCard
            icon={Clock}
            label="마감 임박"
            value={summary.deadlineSoon}
            color="text-amber-600"
            bgColor="bg-amber-50"
          />
          <SummaryCard
            icon={CheckCircle2}
            label="GO 판정"
            value={summary.goCount}
            color="text-green-600"
            bgColor="bg-green-50"
          />
          <SummaryCard
            icon={BarChart3}
            label="분석 완료"
            value={summary.totalAnalyzed}
            color="text-purple-600"
            bgColor="bg-purple-50"
          />
        </motion.div>

        {/* Placeholder for future: Smart Fit Top 5, Deadline list, Weekly summary */}
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-2">Smart Fit Top 5</h2>
          <p className="text-sm text-slate-500">회사 문서를 등록하면 가장 잘 맞는 공고를 자동으로 추천해드려요.</p>
        </div>
      </div>
    </motion.div>
  );
};

export default DashboardPage;
