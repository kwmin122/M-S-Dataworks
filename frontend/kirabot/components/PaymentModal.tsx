import React, { useState, useCallback } from 'react';
import { X, CreditCard, Shield, Check } from 'lucide-react';
import { registerBillingKey, verifyPaymentAmount } from '../services/kiraApiService';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  plan: 'pro';
  username?: string;
}

const STORE_ID = import.meta.env.VITE_PORTONE_STORE_ID;
const CHANNEL_KEY = import.meta.env.VITE_PORTONE_CHANNEL_KEY;

const PaymentModal: React.FC<PaymentModalProps> = ({ isOpen, onClose, onSuccess, plan, username }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState<'confirm' | 'processing' | 'done'>('confirm');

  const handlePayment = useCallback(async () => {
    setError('');
    setLoading(true);
    setStep('processing');

    try {
      if (!STORE_ID || !CHANNEL_KEY) {
        throw new Error('결제 설정이 완료되지 않았습니다. 관리자에게 문의하세요.');
      }

      // Step 1: 서버사이드 금액 검증
      await verifyPaymentAmount(plan);

      // Step 2: PortOne SDK 빌링키 발급
      const PortOne = await import('@portone/browser-sdk/v2');
      const issueResponse = await PortOne.requestIssueBillingKey({
        storeId: STORE_ID,
        channelKey: CHANNEL_KEY,
        billingKeyMethod: 'CARD',
        issueId: `billing_${username || 'anon'}_${Date.now()}`,
        issueName: `KiraBot ${plan.charAt(0).toUpperCase() + plan.slice(1)} 정기결제`,
        customer: {
          customerId: username || `kira_user_${Date.now()}`,
        },
      });

      if (issueResponse.code != null) {
        throw new Error(issueResponse.message || '카드 등록에 실패했습니다.');
      }

      const billingKey = issueResponse.billingKey;
      if (!billingKey) {
        throw new Error('빌링키를 받지 못했습니다.');
      }

      // Step 3: 백엔드에 빌링키 등록
      await registerBillingKey({
        billingKey,
        plan,
        cardLast4: '',
      });

      setStep('done');
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : '결제 처리 중 오류가 발생했습니다.');
      setStep('confirm');
    } finally {
      setLoading(false);
    }
  }, [plan, onSuccess, onClose, username]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl p-8">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600">
          <X size={24} />
        </button>

        {step === 'done' ? (
          <div className="flex flex-col items-center text-center py-8">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 mb-4">
              <Check size={32} />
            </div>
            <h2 className="text-xl font-bold text-slate-900 mb-2">구독이 시작되었습니다!</h2>
            <p className="text-slate-600">Pro 플랜의 모든 기능을 이용하실 수 있습니다.</p>
          </div>
        ) : (
          <div className="flex flex-col items-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-600 text-white mb-6">
              <CreditCard size={28} />
            </div>

            <h2 className="text-2xl font-bold text-slate-900 mb-2">Pro 플랜 구독</h2>
            <p className="text-slate-600 mb-6">정기결제 카드를 등록합니다.</p>

            <div className="w-full rounded-xl bg-slate-50 p-4 mb-6 text-left">
              <div className="flex justify-between mb-2">
                <span className="text-sm text-slate-500">플랜</span>
                <span className="text-sm font-semibold text-slate-900">Pro</span>
              </div>
              <div className="flex justify-between mb-2">
                <span className="text-sm text-slate-500">결제 금액</span>
                <span className="text-sm font-semibold text-slate-900">99,000원/월</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-slate-500">결제 방식</span>
                <span className="text-sm text-slate-700">매월 자동 결제</span>
              </div>
            </div>

            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-6">
              <Shield size={14} />
              <span>TossPayments 안전결제 · 언제든 해지 가능</span>
            </div>

            <button
              onClick={handlePayment}
              disabled={loading}
              className="w-full rounded-xl bg-primary-600 py-3 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {loading ? '처리 중...' : '카드 등록하고 구독 시작'}
            </button>

            {error && (
              <p className="mt-4 w-full rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-left text-xs text-rose-700">
                {error}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PaymentModal;
