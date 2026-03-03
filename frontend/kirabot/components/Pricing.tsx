import React from 'react';

const tiers = [
  {
    label: 'FREE',
    price: '₩0',
    sub: '무료로 시작하세요',
    features: [
      '월 5건 공고 분석',
      '나라장터 공고 검색',
      '기본 자격요건 추출',
      'RFP 요약 리포트',
    ],
    cta: '무료로 시작하기',
    featured: false,
    action: 'start' as const,
  },
  {
    label: 'PRO',
    price: '₩99,000',
    sub: '/ 월',
    features: [
      '무제한 공고 분석',
      'GO/NO-GO 자동 판단',
      'AI 제안서 자동 생성',
      'PPT · WBS · 실적기술서',
      '맞춤 공고 알림',
    ],
    cta: '시작하기',
    featured: true,
    action: 'pro' as const,
  },
  {
    label: 'ENTERPRISE',
    price: '별도 협의',
    sub: '기업 맞춤 플랜',
    features: [
      'Pay 플랜 전체 기능',
      '전담 학습 모델 구축',
      '온프레미스 배포 옵션',
      'SLA 보장 + 전담 지원',
    ],
    cta: '문의하기',
    featured: false,
    action: 'enterprise' as const,
  },
];

interface PricingProps {
  onSelectPro?: () => void;
  onStart?: () => void;
  onEnterprise?: () => void;
}

const Pricing: React.FC<PricingProps> = ({ onSelectPro, onStart, onEnterprise }) => {
  const handleClick = (action: string) => {
    if (action === 'pro' && onSelectPro) onSelectPro();
    else if (action === 'start' && onStart) onStart();
    else if (action === 'enterprise') {
      if (onEnterprise) onEnterprise();
      else window.location.href = 'mailto:contact@mssolutions.kr?subject=Enterprise 플랜 문의';
    }
  };

  return (
    <section id="pricing" className="bg-white py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-16">
          <p className="text-xs font-bold tracking-[0.2em] text-[#0000FF] mb-4">
            PRICING
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-[42px] font-black text-black tracking-tight leading-tight">
            합리적인 요금,
            <br />
            필요한 만큼.
          </h2>
        </div>

        {/* 3 Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-5xl mx-auto">
          {tiers.map((tier) => (
            <div
              key={tier.label}
              className={`rounded p-8 flex flex-col justify-between ${
                tier.featured
                  ? 'bg-[#0000FF]'
                  : tier.label === 'ENTERPRISE'
                    ? 'bg-[#fff7ed]'
                    : 'bg-gray-100'
              }`}
            >
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
                    className={`text-4xl lg:text-5xl font-black ${
                      tier.featured ? 'text-white' : 'text-black'
                    }`}
                  >
                    {tier.price}
                  </span>
                  <span
                    className={`text-sm ${
                      tier.featured ? 'text-white/60' : 'text-gray-600'
                    }`}
                  >
                    {tier.sub}
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
