import React from 'react';
import { Search, FileCheck, BarChart3, Bell, FileSpreadsheet, MessagesSquare } from 'lucide-react';

const features = [
  {
    icon: Search,
    name: '나라장터 실시간 검색',
    description: '키워드, 업무구분, 지역, 금액 조건으로 최대 6개월 공고를 한 번에 검색합니다.',
    iconBg: 'bg-blue-50',
    iconColor: 'text-blue-600',
    hoverBg: 'group-hover:bg-blue-100',
  },
  {
    icon: FileCheck,
    name: '자격요건 자동 추출',
    description: '공고서에서 참가 자격, 기술 인력, 실적 조건, 결격사유를 AI가 자동 추출합니다.',
    iconBg: 'bg-violet-50',
    iconColor: 'text-violet-600',
    hoverBg: 'group-hover:bg-violet-100',
  },
  {
    icon: BarChart3,
    name: 'GO/NO-GO 판단',
    description: '회사 역량과 공고 요건을 매칭하여 입찰 참여 여부를 근거와 함께 추천합니다.',
    iconBg: 'bg-emerald-50',
    iconColor: 'text-emerald-600',
    hoverBg: 'group-hover:bg-emerald-100',
  },
  {
    icon: Bell,
    name: '맞춤 공고 알림',
    description: '관심 키워드와 조건을 설정하면 새 공고를 이메일로 알려드립니다.',
    iconBg: 'bg-amber-50',
    iconColor: 'text-amber-600',
    hoverBg: 'group-hover:bg-amber-100',
  },
  {
    icon: FileSpreadsheet,
    name: '일괄 평가 & 리포트',
    description: '여러 공고를 한 번에 평가하고 결과를 CSV로 내려받아 팀과 공유하세요.',
    iconBg: 'bg-sky-50',
    iconColor: 'text-sky-600',
    hoverBg: 'group-hover:bg-sky-100',
  },
  {
    icon: MessagesSquare,
    name: '문서 기반 Q&A',
    description: '분석된 문서에 대해 자유롭게 질문하면 원문 근거와 페이지를 표시합니다.',
    iconBg: 'bg-rose-50',
    iconColor: 'text-rose-600',
    hoverBg: 'group-hover:bg-rose-100',
  },
];

const Features: React.FC = () => {
  return (
    <section id="product" className="bg-white py-28 sm:py-36">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">

        {/* Header — 토스 스타일 큰 텍스트 */}
        <div className="mb-20">
          <p className="text-sm font-semibold text-primary-600 tracking-wide mb-4">주요 기능</p>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-slate-900 leading-tight font-sans">
            입찰 성공률을 높이는<br />
            <span className="text-primary-600">6가지 AI 기능</span>
          </h2>
        </div>

        {/* 2x3 Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <div
              key={f.name}
              className="group rounded-2xl border border-slate-200 p-8 transition-all duration-200 hover:border-slate-300 hover:shadow-lg hover:-translate-y-0.5"
            >
              <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${f.iconBg} ${f.iconColor} ${f.hoverBg} mb-6 transition-colors duration-200`}>
                <f.icon size={22} strokeWidth={1.8} />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-3 font-sans">{f.name}</h3>
              <p className="text-sm text-slate-500 leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>

        <p className="text-center text-xs text-slate-400 mt-16">
          * AI 응답은 참고용이며, 최종 판단은 사용자의 책임입니다.
        </p>
      </div>
    </section>
  );
};

export default Features;
