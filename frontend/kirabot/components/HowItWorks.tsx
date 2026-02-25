import React from 'react';

const steps = [
  {
    num: '01',
    title: '공고서를 올리세요',
    desc: 'PDF, HWP, Excel, Word — 어떤 형식이든 상관없습니다.\n나라장터에서 직접 검색해도 됩니다.',
    accent: 'from-blue-500 to-cyan-400',
  },
  {
    num: '02',
    title: 'AI가 자격요건을 추출합니다',
    desc: '참가 자격, 기술 인력, 실적 조건, 결격사유까지.\n수백 페이지에서 핵심만 뽑아냅니다.',
    accent: 'from-violet-500 to-purple-400',
  },
  {
    num: '03',
    title: 'GO/NO-GO를 판단하세요',
    desc: '회사 역량과 공고 요건을 비교한 근거 기반 의견.\n입찰 참여 여부를 빠르게 결정할 수 있습니다.',
    accent: 'from-emerald-500 to-teal-400',
  },
];

const HowItWorks: React.FC = () => {
  return (
    <section className="bg-slate-900 py-32 sm:py-40">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">

        {/* 헤더 */}
        <div className="mb-24">
          <p className="text-sm font-semibold text-slate-400 tracking-wide mb-4">이용 방법</p>
          <h2 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight font-sans">
            복잡한 공고 분석,<br />
            세 단계로 끝납니다.
          </h2>
        </div>

        {/* 3 Steps */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 lg:gap-8">
          {steps.map((step) => (
            <div key={step.num} className="group">
              {/* Number */}
              <span className={`text-6xl sm:text-7xl font-extrabold bg-gradient-to-r ${step.accent} bg-clip-text text-transparent`}>
                {step.num}
              </span>
              {/* Divider */}
              <div className={`h-1 w-16 mt-6 mb-6 rounded-full bg-gradient-to-r ${step.accent}`} />
              {/* Title */}
              <h3 className="text-2xl font-bold text-white mb-4 font-sans">
                {step.title}
              </h3>
              {/* Description */}
              <p className="text-base text-slate-400 leading-relaxed whitespace-pre-line">
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
