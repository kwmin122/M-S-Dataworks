import React from 'react';
import { Upload, MessageSquareText, Highlighter, Scale, LayoutDashboard } from 'lucide-react';

const features = [
  {
    name: '문서 업로드 & 분석',
    description: 'PDF, DOCX, TXT 문서를 업로드하면 자동으로 구조화합니다.',
    icon: Upload,
  },
  {
    name: 'PDF 기반 질의응답',
    description: '업로드한 문서에 대해 자연어로 질문하면 관련 내용을 찾아 답변합니다.',
    icon: MessageSquareText,
  },
  {
    name: '근거 하이라이트',
    description: '답변의 근거를 원본 문서에서 직접 확인할 수 있습니다.',
    icon: Highlighter,
  },
  {
    name: '의견 모드',
    description: '보수적 / 균형 / 공격적 — 상황에 맞는 톤으로 AI 의견을 제공합니다.',
    icon: Scale,
  },
  {
    name: '관리자 대시보드',
    description: '사용 현황, 문서 통계, 시스템 상태를 한 화면에서 확인합니다.',
    icon: LayoutDashboard,
  },
];

const Features: React.FC = () => {
  return (
    <div id="product" className="bg-white py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:text-center">
          <h2 className="text-base font-semibold leading-7 text-primary-600">Product</h2>
          <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl font-sans">
            문서를 업로드하면,<br/>
            <span className="text-primary-600">근거</span>와 함께 AI가 읽고 답합니다.
          </p>
        </div>
        <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
          <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-16 lg:max-w-none lg:grid-cols-3">
            {features.map((feature) => (
              <div key={feature.name} className="flex flex-col bg-slate-50 rounded-2xl p-8 transition-colors hover:bg-slate-100">
                <dt className="flex items-center gap-x-3 text-lg font-bold leading-7 text-slate-900 mb-4">
                  <div className="p-2 bg-white rounded-lg shadow-sm text-primary-600">
                    <feature.icon className="h-6 w-6" aria-hidden="true" />
                  </div>
                  {feature.name}
                </dt>
                <dd className="flex flex-auto flex-col text-base leading-7 text-slate-600">
                  <p className="flex-auto">{feature.description}</p>
                </dd>
              </div>
            ))}
          </dl>
          <p className="text-center text-xs text-slate-400 mt-12">
            * AI 응답은 참고용이며, 최종 판단은 사용자의 책임입니다.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Features;