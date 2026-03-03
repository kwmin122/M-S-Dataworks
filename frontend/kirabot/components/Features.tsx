import React from 'react';

const layers = [
  {
    tag: 'LAYER 1',
    title: '전문가 노하우',
    stat: '495+',
    unit: '지식 유닛 탑재',
    lines: [
      '유튜브 강의 · 블로그 · 공식 가이드',
      '평가위원 심리, 감점 요소, 제안 구조',
      '모든 사용자에게 공통 적용',
    ],
  },
  {
    tag: 'LAYER 2',
    title: '회사 맞춤 학습',
    stat: '92%',
    unit: '학습도 도달 가능',
    lines: [
      '과거 제안서 → 문체·구조·강점 분석',
      'AI 수정 diff → 패턴 자동 학습',
      '수정률 45% → 8%로 수렴',
    ],
  },
  {
    tag: 'LAYER 3',
    title: '승패 분석',
    stat: 'WIN',
    unit: '승패 패턴 자동 추출',
    lines: [
      '낙찰 vs 탈락 제안서 비교 분석',
      '경쟁사 낙찰 패턴 인사이트',
      '입찰할수록 데이터 축적 → 플라이휠',
    ],
  },
];

const Features: React.FC = () => {
  return (
    <section id="product" className="bg-[#0A0A0A] py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Header */}
        <div className="mb-16">
          <p className="text-xs font-bold tracking-[0.2em] text-[#0000FF] mb-4">
            AI LEARNING ENGINE
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-[42px] font-black text-white tracking-tight leading-tight mb-6">
            쓸수록 똑똑해지는
            <br />
            3계층 학습 모델.
          </h2>
          <p className="text-sm text-gray-500 leading-relaxed max-w-xl">
            전문가 50명분 노하우 + 귀사 맞춤 학습 + 승패 분석.
            <br />
            매 입찰마다 더 정확해지는 AI.
          </p>
        </div>

        {/* 3 Layer Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {layers.map((layer) => (
            <div
              key={layer.tag}
              className="bg-[#151515] rounded p-6 lg:p-8"
            >
              <p className="text-[10px] font-bold tracking-[0.2em] text-[#0000FF] mb-3">
                {layer.tag}
              </p>
              <h3 className="text-xl font-black text-white mb-2">
                {layer.title}
              </h3>
              <span className="text-5xl lg:text-6xl font-black text-[#0000FF] leading-none">
                {layer.stat}
              </span>
              <p className="text-sm text-gray-500 mt-4 mb-4">{layer.unit}</p>
              <div className="space-y-2">
                {layer.lines.map((line) => (
                  <p key={line} className="text-xs text-gray-600 leading-relaxed">
                    {line}
                  </p>
                ))}
              </div>
            </div>
          ))}
        </div>

        <p className="text-center text-xs text-gray-600 mt-16">
          * AI 응답은 참고용이며, 최종 판단은 사용자의 책임입니다.
        </p>
      </div>
    </section>
  );
};

export default Features;
