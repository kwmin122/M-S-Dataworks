import React from 'react';
import Button from './Button';

const tiers = [
  {
    name: "Free",
    price: "0",
    unit: "원/월",
    features: [
      "사용자 1명",
      "월 3회 분석",
      "문서 5개 저장",
      "기본 Q&A"
    ],
    cta: "시작하기",
    featured: false
  },
  {
    name: "Pro",
    price: "99,000",
    unit: "원/월",
    features: [
      "사용자 5명",
      "월 50회 분석",
      "문서 100개 저장",
      "의견 모드 포함",
      "PDF 하이라이트"
    ],
    cta: "시작하기",
    featured: true
  },
  {
    name: "Enterprise",
    price: "별도 협의",
    unit: "",
    features: [
      "사용자 무제한",
      "무제한 분석",
      "전용 스토리지",
      "관리자 대시보드",
      "전담 지원"
    ],
    cta: "문의하기",
    featured: false
  }
];

interface PricingProps {
  onSelectPro?: () => void;
  onStart?: () => void;
}

const Pricing: React.FC<PricingProps> = ({ onSelectPro, onStart }) => {
  return (
    <div id="pricing" className="py-24 bg-white border-t border-slate-200">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            합리적인 요금, 필요한 만큼
          </h2>
          <p className="mt-4 text-lg leading-8 text-slate-600">
            초기 비용 없이 시작하고, 비즈니스 성장에 맞춰 확장하세요.
          </p>
        </div>
        
        <div className="mx-auto grid max-w-md grid-cols-1 gap-8 lg:mx-0 lg:max-w-none lg:grid-cols-3">
          {tiers.map((tier) => (
            <div 
              key={tier.name} 
              className={`flex flex-col justify-between rounded-3xl p-8 ring-1 xl:p-10 ${
                tier.featured 
                  ? 'bg-slate-900 ring-slate-900 shadow-2xl scale-105 z-10' 
                  : 'bg-white ring-slate-200 shadow-lg'
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-x-4">
                  <h3 className={`text-lg font-semibold leading-8 ${tier.featured ? 'text-white' : 'text-slate-900'}`}>
                    {tier.name}
                  </h3>
                </div>
                <p className={`mt-4 flex items-baseline gap-x-1 ${tier.featured ? 'text-white' : 'text-slate-900'}`}>
                  <span className="text-4xl font-bold tracking-tight">{tier.price}</span>
                  <span className={`text-sm font-semibold ${tier.featured ? 'text-slate-300' : 'text-slate-600'}`}>{tier.unit}</span>
                </p>
                <ul role="list" className={`mt-8 space-y-3 text-sm leading-6 ${tier.featured ? 'text-slate-300' : 'text-slate-600'}`}>
                  {tier.features.map((feature) => (
                    <li key={feature} className="flex gap-x-3">
                      <svg className={`h-6 w-5 flex-none ${tier.featured ? 'text-primary-400' : 'text-primary-600'}`} viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                      </svg>
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
              <Button
                variant={tier.featured ? 'secondary' : 'primary'}
                className={`mt-8 w-full ${tier.featured ? 'bg-white text-slate-900 hover:bg-slate-100' : ''}`}
                size="md"
                onClick={() => {
                  if (tier.name === 'Pro' && onSelectPro) onSelectPro();
                  else if (tier.name === 'Free' && onStart) onStart();
                }}
              >
                {tier.cta}
              </Button>
            </div>
          ))}
        </div>
        
        <p className="mt-10 text-center text-xs text-slate-500">
          VAT 별도. 요금제는 사전 공지 후 변경될 수 있습니다.
        </p>
      </div>
    </div>
  );
};

export default Pricing;