import React, { useEffect, useState } from 'react';
import { CreditCard, Calendar, AlertCircle } from 'lucide-react';
import { getSubscription, cancelSubscription } from '../../services/kiraApiService';
import type { Subscription } from '../../types';
import EmptyState from '../shared/EmptyState';

const SubscriptionPage: React.FC = () => {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    getSubscription()
      .then(setSub)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleCancel = async () => {
    if (!confirm('정말 구독을 해지하시겠습니까? 현재 결제 기간이 끝날 때까지 서비스를 이용할 수 있습니다.')) return;
    setCancelling(true);
    try {
      const updated = await cancelSubscription();
      setSub(updated);
    } catch (e) {
      alert(e instanceof Error ? e.message : '해지 실패');
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="flex gap-1">
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
        </div>
      </div>
    );
  }

  if (!sub || sub.status === 'none') {
    return (
      <EmptyState
        icon={CreditCard}
        title="구독 정보가 없습니다"
        description="Pro 플랜을 구독하면 모든 기능을 이용할 수 있습니다."
      />
    );
  }

  const isActive = sub.status === 'active';
  const periodEnd = sub.currentPeriodEnd
    ? new Date(sub.currentPeriodEnd).toLocaleDateString('ko-KR')
    : '-';

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-1">구독 관리</h2>
        <p className="text-sm text-slate-500">현재 구독 상태와 결제 정보를 확인할 수 있습니다.</p>
      </div>

      <div className="rounded-xl border border-slate-200 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`rounded-full px-3 py-1 text-xs font-bold ${
              isActive ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
            }`}>
              {isActive ? 'Active' : '해지 예정'}
            </div>
            <h3 className="text-base font-semibold text-slate-900">
              {sub.plan === 'pro' ? 'Pro' : 'Free'} 플랜
            </h3>
          </div>
          <span className="text-lg font-bold text-slate-900">
            {sub.priceKrw?.toLocaleString('ko-KR')}원/월
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          {sub.cardLast4 && (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <CreditCard size={16} className="text-slate-400" />
              <span>카드 끝 4자리: {sub.cardLast4}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Calendar size={16} className="text-slate-400" />
            <span>다음 결제일: {periodEnd}</span>
          </div>
        </div>

        {sub.status === 'cancelled' && (
          <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3">
            <AlertCircle size={16} className="text-amber-600 mt-0.5 shrink-0" />
            <p className="text-sm text-amber-700">
              구독이 해지되었습니다. {periodEnd}까지 서비스를 이용할 수 있습니다.
            </p>
          </div>
        )}

        {isActive && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="text-sm text-slate-500 hover:text-red-600 transition-colors"
          >
            {cancelling ? '처리 중...' : '구독 해지'}
          </button>
        )}
      </div>
    </div>
  );
};

export default SubscriptionPage;
