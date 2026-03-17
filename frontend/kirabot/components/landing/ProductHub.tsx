import React from 'react';
import { Search, PenTool, TrendingUp, Building2, ArrowRight } from 'lucide-react';

interface HubCardProps {
  icon: React.ElementType;
  title: string;
  description: string;
  cta: string;
  size: 'primary' | 'secondary';
  onClick: () => void;
  badge?: string;
  disabled?: boolean;
}

function HubCard({ icon: Icon, title, description, cta, size, onClick, badge, disabled }: HubCardProps) {
  const isPrimary = size === 'primary';

  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`
        group relative text-left rounded-2xl border transition-all duration-200
        ${isPrimary
          ? 'p-8 lg:p-10 border-slate-200 bg-white shadow-sm hover:shadow-lg hover:-translate-y-1'
          : 'p-6 lg:p-8 border-slate-200/80 bg-white/80 shadow-sm hover:shadow-md hover:-translate-y-0.5'
        }
        ${disabled ? 'opacity-60 cursor-not-allowed hover:translate-y-0 hover:shadow-sm' : 'cursor-pointer'}
      `}
    >
      {badge && (
        <span className="absolute top-4 right-4 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-kira-100 text-kira-700">
          {badge}
        </span>
      )}

      <div className={`mb-4 ${isPrimary ? 'text-kira-500' : 'text-slate-400'}`}>
        <Icon size={isPrimary ? 32 : 24} strokeWidth={1.5} />
      </div>

      <h3 className={`font-semibold text-slate-900 ${isPrimary ? 'text-xl' : 'text-base'}`}>
        {title}
      </h3>

      <p className={`mt-2 text-slate-500 leading-relaxed ${isPrimary ? 'text-sm' : 'text-xs'}`}>
        {description}
      </p>

      <span className={`
        mt-4 inline-flex items-center font-medium
        ${isPrimary
          ? 'text-sm text-kira-600 group-hover:text-kira-700'
          : 'text-xs text-slate-500 group-hover:text-slate-700'
        }
        ${disabled ? '' : 'group-hover:gap-2'}
        gap-1 transition-all duration-200
      `}>
        {cta}
        <ArrowRight size={isPrimary ? 16 : 14} className="transition-transform duration-200 group-hover:translate-x-0.5" />
      </span>
    </button>
  );
}

interface ProductHubProps {
  onNavigateChat: () => void;
  onNavigateStudio: () => void;
  onNavigateForecast: () => void;
  onNavigateCompany: () => void;
  studioEnabled?: boolean;
}

export default function ProductHub({
  onNavigateChat,
  onNavigateStudio,
  onNavigateForecast,
  onNavigateCompany,
  studioEnabled = false,
}: ProductHubProps) {
  return (
    <section className="bg-slate-50 py-20 lg:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12 lg:mb-16">
          <h2 className="text-2xl lg:text-3xl font-bold text-slate-900 tracking-tight">
            무엇을 도와드릴까요?
          </h2>
          <p className="mt-3 text-base text-slate-500">
            공공조달 입찰의 모든 단계를 AI와 함께 진행하세요.
          </p>
        </div>

        {/* 1차 축: 대형 카드 2개 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <HubCard
            icon={Search}
            title="공고 탐색"
            description="나라장터 공고 검색, AI 분석, 자격요건 추출, GO/NO-GO 판단을 빠르게 진행합니다."
            cta="시작하기"
            size="primary"
            onClick={onNavigateChat}
          />
          <HubCard
            icon={PenTool}
            title="입찰 문서 작성"
            description="제안서, 수행계획서, PPT, 실적기술서를 AI가 학습하여 자동 생성하고 개선합니다."
            cta="Studio 열기"
            size="primary"
            onClick={onNavigateStudio}
            badge={studioEnabled ? undefined : '곧 오픈'}
            disabled={!studioEnabled}
          />
        </div>

        {/* 2차 축: 보조 카드 2개 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <HubCard
            icon={TrendingUp}
            title="발주 예측"
            description="발주 시기와 수요 흐름을 분석해 선제적으로 대응합니다."
            cta="둘러보기"
            size="secondary"
            onClick={onNavigateForecast}
          />
          <HubCard
            icon={Building2}
            title="회사 역량 관리"
            description="실적, 인력, 기술, 스타일 자산을 회사 공통 DB로 관리합니다."
            cta="설정"
            size="secondary"
            onClick={onNavigateCompany}
          />
        </div>
      </div>
    </section>
  );
}
