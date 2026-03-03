import React from 'react';

const steps = [
  {
    num: '01',
    title: '공고서를 올리세요',
    desc: 'PDF, HWP, Excel, Word —\n어떤 형식이든 업로드하세요.\n나라장터에서 직접 검색도 가능합니다.',
  },
  {
    num: '02',
    title: 'AI가 자격요건을 추출합니다',
    desc: '지역, 업종, 기술, 금액, 인력, 실적 등\n수백 페이지에서 핵심만 자동 추출합니다.',
  },
  {
    num: '03',
    title: 'GO/NO-GO를 판단하세요',
    desc: '회사 역량과 공고 요건을 비교하여\n입찰 참여 여부를 근거와 함께 제시합니다.',
  },
];

const HowItWorks: React.FC = () => {
  return (
    <section className="bg-white py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-20">
          <p className="text-xs font-bold tracking-[0.2em] text-[#0000FF] mb-4">
            HOW IT WORKS
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-[42px] font-black text-black tracking-tight leading-tight">
            복잡한 공고 분석,
            <br />
            세 단계로 끝납니다.
          </h2>
        </div>

        {/* 3 Steps */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-16 lg:gap-12">
          {steps.map((step) => (
            <div key={step.num}>
              <span className="text-6xl sm:text-7xl lg:text-8xl font-black text-[#0000FF] leading-none">
                {step.num}
              </span>
              <h3 className="text-lg font-bold text-black mt-6 mb-3">
                {step.title}
              </h3>
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
                {step.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;
