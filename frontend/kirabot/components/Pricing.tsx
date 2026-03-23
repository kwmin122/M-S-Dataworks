import React, { useState } from 'react';

type PlanAction = 'start' | 'starter' | 'pro' | 'enterprise';

interface TierDef {
  label: string;
  monthlyPrice: string;
  annualPrice?: string;
  sub: string;
  annualSub?: string;
  features: string[];
  cta: string;
  featured: boolean;
  action: PlanAction;
}

const tiers: TierDef[] = [
  {
    label: 'FREE',
    monthlyPrice: '₩0',
    sub: '무료로 시작하세요',
    features: [
      '월 5건 공고 분석',
      '나라장터 공고 검색',
      '기본 자격요건 추출',
      'RFP 요약 리포트',
    ],
    cta: '무료로 시작하기',
    featured: false,
    action: 'start',
  },
  {
    label: 'STARTER',
    monthlyPrice: '₩49,000',
    annualPrice: '₩39,000',
    sub: '/ 월',
    annualSub: '/ 월 (연간 결제)',
    features: [
      '월 30건 공고 분석',
      '월 5건 AI 문서 생성',
      'GO/NO-GO 자동 판단',
      '맞춤 공고 알림 3세트',
      'DOCX 다운로드',
    ],
    cta: '시작하기',
    featured: false,
    action: 'starter',
  },
  {
    label: 'PRO',
    monthlyPrice: '₩149,000',
    annualPrice: '₩119,000',
    sub: '/ 월',
    annualSub: '/ 월 (연간 결제)',
    features: [
      '무제한 공고 분석',
      '월 20건 AI 문서 생성',
      '회사 맞춤 학습 (Layer 2)',
      'PPT · WBS · 실적기술서',
      '맞춤 공고 알림 10세트',
      '수정 학습 (Relearn)',
    ],
    cta: '시작하기',
    featured: true,
    action: 'pro',
  },
  {
    label: 'ENTERPRISE',
    monthlyPrice: '별도 협의',
    sub: '기업 맞춤 플랜',
    features: [
      'Pro 플랜 전체 기능',
      '전담 학습 모델 구축',
      '온프레미스 배포 옵션',
      'SLA 보장 + 전담 지원',
    ],
    cta: '문의하기',
    featured: false,
    action: 'enterprise',
  },
];

interface PricingProps {
  onSelectPro?: () => void;
  onSelectStarter?: () => void;
  onStart?: () => void;
  onEnterprise?: () => void;
}

const Pricing: React.FC<PricingProps> = ({ onSelectPro, onSelectStarter, onStart, onEnterprise }) => {
  const [annual, setAnnual] = useState(false);

  const handleClick = (action: PlanAction) => {
    if (action === 'pro' && onSelectPro) onSelectPro();
    else if (action === 'starter' && onSelectStarter) onSelectStarter();
    else if (action === 'start' && onStart) onStart();
    else if (action === 'enterprise') {
      if (onEnterprise) onEnterprise();
      else window.location.href = 'mailto:contact@mssolutions.kr?subject=Enterprise 플랜 문의';
    }
  };

  const getDisplayPrice = (tier: TierDef) => {
    if (annual && tier.annualPrice) return tier.annualPrice;
    return tier.monthlyPrice;
  };

  const getDisplaySub = (tier: TierDef) => {
    if (annual && tier.annualSub) return tier.annualSub;
    return tier.sub;
  };

  return (
    <section id="pricing" className="bg-white py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-10">
          <p className="text-xs font-bold tracking-[0.2em] text-[#0000FF] mb-4">
            PRICING
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-[42px] font-black text-black tracking-tight leading-tight">
            합리적인 요금,
            <br />
            필요한 만큼.
          </h2>
        </div>

        {/* Annual / Monthly Toggle */}
        <div className="flex items-center justify-center gap-3 mb-12">
          <span className={`text-sm font-medium ${!annual ? 'text-black' : 'text-gray-400'}`}>
            월간
          </span>
          <button
            onClick={() => setAnnual(!annual)}
            className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
              annual ? 'bg-[#0000FF]' : 'bg-gray-300'
            }`}
            aria-label="연간/월간 결제 전환"
          >
            <span
              className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                annual ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
          <span className={`text-sm font-medium ${annual ? 'text-black' : 'text-gray-400'}`}>
            연간
          </span>
          {annual && (
            <span className="ml-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
              최대 20% 할인
            </span>
          )}
        </div>

        {/* 4 Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 max-w-6xl mx-auto">
          {tiers.map((tier) => (
            <div
              key={tier.label}
              className={`relative rounded p-8 flex flex-col justify-between ${
                tier.featured
                  ? 'bg-[#0000FF]'
                  : tier.label === 'ENTERPRISE'
                    ? 'bg-[#fff7ed]'
                    : 'bg-gray-100'
              }`}
            >
              {tier.featured && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-white px-3 py-1 text-xs font-bold text-[#0000FF] shadow-sm">
                  추천
                </span>
              )}
              <div>
                <p
                  className={`text-xs font-bold tracking-[0.2em] mb-6 ${
                    tier.featured ? 'text-white/60' : 'text-gray-600'
                  }`}
                >
                  {tier.label}
                </p>
                <div className="flex items-baseline gap-2 mb-1">
                  <span
                    className={`text-3xl lg:text-4xl font-black ${
                      tier.featured ? 'text-white' : 'text-black'
                    }`}
                  >
                    {getDisplayPrice(tier)}
                  </span>
                  <span
                    className={`text-sm ${
                      tier.featured ? 'text-white/60' : 'text-gray-600'
                    }`}
                  >
                    {getDisplaySub(tier)}
                  </span>
                </div>
                <div
                  className={`h-px my-6 ${
                    tier.featured ? 'bg-white/20' : 'bg-gray-200'
                  }`}
                />
                <ul className="space-y-3">
                  {tier.features.map((f) => (
                    <li
                      key={f}
                      className={`text-sm ${
                        tier.featured ? 'text-white' : 'text-gray-500'
                      }`}
                    >
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
              <button
                onClick={() => handleClick(tier.action)}
                className={`mt-8 w-full py-3 rounded text-sm font-semibold transition-colors ${
                  tier.featured
                    ? 'bg-white text-[#0000FF] hover:bg-gray-100'
                    : 'bg-white text-black border border-gray-200 hover:bg-gray-50'
                }`}
              >
                {tier.cta}
              </button>
            </div>
          ))}
        </div>

        <p className="mt-10 text-center text-xs text-gray-600">
          VAT 별도. 요금제는 사전 공지 후 변경될 수 있습니다.
        </p>
      </div>
    </section>
  );
};

export default Pricing;
