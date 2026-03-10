import React from 'react';
import { ArrowLeft, Play, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useActiveConversation } from '../../hooks/useActiveConversation';

interface UserGuideProps {
  onClose: () => void;
  onStartCompanyDB?: () => void;
}

interface Capability {
  emoji: string;
  name: string;
  description: string;
  howLabel: string;
  howColor: string;
  howBg: string;
  iconBg: string;
  instructions: string[];
}

const capabilities: Capability[] = [
  {
    emoji: '🏢',
    name: '회사 역량 DB 구축',
    description: '모든 기능의 품질을 결정하는 핵심 단계입니다. 회사 정보가 없으면 범용 문서만 생성되고, 회사 정보가 있으면 우리 회사에 딱 맞는 맞춤형 문서가 생성됩니다.',
    howLabel: '가장 먼저 해주세요',
    howColor: 'text-amber-600',
    howBg: 'bg-amber-50',
    iconBg: 'bg-amber-50',
    instructions: [
      "채팅 시작 화면에서 '회사 역량 DB 구축' 버튼을 클릭하세요.",
      '회사소개서, 실적증명서, 인력현황, 과거 제안서 등을 업로드합니다.',
      'AI가 자동으로 분석\xB7정리하여 이후 모든 문서(제안서, WBS, PPT, 실적기술서)에 반영합니다.',
    ],
  },
  {
    emoji: '🔍',
    name: '공고 검색',
    description: '나라장터에서 키워드로 입찰 공고를 찾아줍니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-blue-500',
    howBg: 'bg-blue-50',
    iconBg: 'bg-blue-50',
    instructions: [
      '채팅창에 찾고 싶은 키워드를 입력하세요.',
      '예: "AI 소프트웨어 공고 검색해줘"',
    ],
  },
  {
    emoji: '📋',
    name: 'RFP 분석',
    description: '공고 문서에서 자격요건을 추출하고 핵심 내용을 요약합니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-orange-500',
    howBg: 'bg-orange-50',
    iconBg: 'bg-orange-50',
    instructions: [
      '방법 1: 검색 결과에서 공고를 클릭 — 첨부파일이 자동 분석됩니다.',
      '방법 2: 클립 버튼으로 PDF/HWP 파일을 직접 업로드하세요.',
    ],
  },
  {
    emoji: '✅',
    name: 'GO/NO-GO 자동 판단',
    description: '회사 자격요건과 공고 요건을 AI가 자동 비교합니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-emerald-500',
    howBg: 'bg-emerald-50',
    iconBg: 'bg-emerald-50',
    instructions: [
      "먼저 '회사 역량 DB'에 실적\xB7인력 정보를 등록하세요.",
      '공고를 분석하면 GO/NO-GO 결과가 자동으로 표시됩니다.',
      '요건별 충족 여부를 한눈에 확인할 수 있어요.',
    ],
  },
  {
    emoji: '📝',
    name: '제안서 DOCX 생성',
    description: 'RFP 분석 결과 + 회사 역량을 기반으로 맞춤 제안서를 생성합니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-blue-600',
    howBg: 'bg-blue-50',
    iconBg: 'bg-blue-50',
    instructions: [
      "공고 분석이 완료되면 '제안서 v2 생성' 버튼이 나타납니다.",
      '클릭하면 AI가 섹션별 제안서를 자동 작성합니다.',
      '완성된 DOCX 파일을 다운로드하여 수정\xB7제출하세요.',
    ],
  },
  {
    emoji: '📊',
    name: 'WBS \xB7 PPT \xB7 실적기술서',
    description: '수행계획서, 발표자료, 실적기술서를 한 번에 만들어줍니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-purple-500',
    howBg: 'bg-purple-50',
    iconBg: 'bg-purple-50',
    instructions: [
      '공고 분석 완료 후 각 버튼이 활성화됩니다.',
      "'WBS 생성' → 수행계획서(DOCX) + 엑셀(XLSX) + 간트차트(PNG)",
      "'PPT 생성' → 발표자료(PPTX) + 예상질문 10개",
      "'실적기술서' → 회사 DB 기반 맞춤 기술서(DOCX)",
    ],
  },
  {
    emoji: '✏️',
    name: '제안서 직접 수정 & AI 학습',
    description: 'AI가 생성한 제안서를 섹션별로 수정할 수 있습니다. 수정 내용은 AI가 학습하여 다음 생성 시 자동 반영됩니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-teal-500',
    howBg: 'bg-teal-50',
    iconBg: 'bg-teal-50',
    instructions: [
      "상단 '문서 관리' → '제안서' 탭에서 섹션별 내용을 확인합니다.",
      '각 섹션을 직접 편집하고 저장하세요.',
      "'DOCX 재생성' 버튼으로 수정된 내용으로 새 문서를 만듭니다.",
      '수정을 3회 이상 반복하면 AI가 패턴을 학습하여 다음부터 자동 반영합니다.',
    ],
  },
  {
    emoji: '✅',
    name: '제출 체크리스트',
    description: 'RFP에서 필수/선택 제출서류를 자동 추출하여 누락을 방지합니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-cyan-500',
    howBg: 'bg-cyan-50',
    iconBg: 'bg-cyan-50',
    instructions: [
      "공고 분석 완료 후 '체크리스트' 버튼을 클릭하세요.",
      '필수 제출서류와 선택 제출서류가 분리되어 표시됩니다.',
      '입찰 제출 전 빠진 서류가 없는지 확인할 수 있습니다.',
    ],
  },
  {
    emoji: '💬',
    name: '문서 기반 Q&A',
    description: '분석된 문서에 대해 자유롭게 질문하면 AI가 답변합니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-indigo-500',
    howBg: 'bg-indigo-50',
    iconBg: 'bg-indigo-50',
    instructions: [
      '공고 분석이 완료되면 자동으로 Q&A 모드로 전환됩니다.',
      '채팅창에 궁금한 점을 자유롭게 입력하세요.',
      '예: "이 공고의 평가 배점 기준이 뭐야?", "사업비 제한이 있어?"',
    ],
  },
  {
    emoji: '📦',
    name: '일괄 평가 & CSV 내보내기',
    description: '여러 공고를 한 번에 GO/NO-GO 평가하고, 검색 결과를 CSV로 내려받을 수 있습니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-sky-500',
    howBg: 'bg-sky-50',
    iconBg: 'bg-sky-50',
    instructions: [
      '공고 검색 결과에서 원하는 공고들을 체크하세요.',
      "'일괄 평가' 버튼을 누르면 선택한 공고들을 동시에 GO/NO-GO 판단합니다.",
      "'CSV' 버튼으로 검색 결과를 엑셀 파일로 내려받을 수 있습니다.",
    ],
  },
  {
    emoji: '🔔',
    name: '알림 설정',
    description: '관심 분야의 새 공고가 등록되면 이메일로 알려드립니다.',
    howLabel: '이렇게 하세요',
    howColor: 'text-rose-500',
    howBg: 'bg-rose-50',
    iconBg: 'bg-rose-50',
    instructions: [
      "사이드바 하단의 '알림 설정' 메뉴를 클릭하세요.",
      '관심 키워드, 업무구분, 지역, 금액 범위 등을 설정합니다.',
      '조건에 맞는 새 공고가 나오면 자동으로 이메일 알림을 받습니다.',
    ],
  },
];

const UserGuide: React.FC<UserGuideProps> = ({ onClose, onStartCompanyDB }) => {
  const { conversation } = useActiveConversation();
  const hasCompanyProfile = Boolean(conversation?.companyProfile?.companyName);
  const companyChunks = conversation?.companyChunks || 0;

  return (
    <div className="flex h-full flex-col bg-[#FAFBFC]">
      {/* Header */}
      <div className="flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-sm">
        <button
          type="button"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          title="채팅으로 돌아가기"
        >
          <ArrowLeft size={18} />
        </button>
        <h2 className="text-sm font-bold text-slate-800">사용 가이드</h2>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[760px] px-6 py-12">
          {/* Hero */}
          <div className="mb-10 text-center">
            <h1 className="mb-3 text-[32px] font-extrabold leading-tight text-slate-900 font-title">
              Kira Bot이 할 수 있는 것들
            </h1>
            <p className="text-base leading-relaxed text-slate-500">
              각 기능은 독립적으로 사용할 수 있습니다.<br />
              필요한 것부터 시작하세요.
            </p>
          </div>

          {/* Company Status Card */}
          {hasCompanyProfile ? (
            <div className="mb-8 rounded-xl border border-green-200 bg-green-50 p-5">
              <div className="flex items-start gap-3">
                <CheckCircle2 size={22} className="mt-0.5 shrink-0 text-green-600" />
                <div>
                  <p className="text-sm font-semibold text-green-900">
                    {conversation.companyProfile.companyName} — {companyChunks}개 문서 등록됨
                  </p>
                  <p className="mt-1 text-sm text-green-700">
                    GO/NO-GO 자동 판단과 맞춤형 제안서 생성이 가능합니다.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="mb-8 rounded-xl border-2 border-amber-300 bg-gradient-to-r from-amber-50 to-orange-50 p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100">
                  <AlertCircle size={20} className="text-amber-600" />
                </div>
                <div className="flex-1">
                  <p className="text-base font-bold text-amber-900">
                    회사 문서를 먼저 등록해주세요!
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-amber-800">
                    회사소개서, 실적증명서, 인력현황을 등록하면<br />
                    <strong>GO/NO-GO 판단 정확도가 2배 이상 향상</strong>되고,<br />
                    제안서\xB7WBS\xB7PPT 모두 <strong>우리 회사에 딱 맞는 맞춤형</strong>으로 생성됩니다.
                  </p>
                  <button
                    type="button"
                    onClick={() => { onClose(); onStartCompanyDB?.(); }}
                    className="mt-3 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 transition-colors"
                  >
                    회사 역량 DB 구축 시작하기
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Capability Cards */}
          <div className="space-y-5">
            {capabilities.map((cap, idx) => (
              <div
                key={cap.name}
                className={`rounded-2xl border p-7 shadow-sm ${
                  idx === 0
                    ? 'border-amber-200 bg-gradient-to-br from-white to-amber-50/50 ring-1 ring-amber-100'
                    : 'border-slate-200 bg-white'
                }`}
              >
                {/* Top: icon + name + description */}
                <div className="flex items-start gap-4">
                  <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px] ${cap.iconBg}`}>
                    <span className="text-[22px]">{cap.emoji}</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-bold text-slate-900 font-title">{cap.name}</h3>
                      {idx === 0 && (
                        <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-white">
                          추천
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-slate-500">{cap.description}</p>
                  </div>
                </div>

                {/* Divider */}
                <div className="my-5 h-px bg-slate-100" />

                {/* How-to */}
                <div>
                  <p className={`mb-2.5 text-xs font-bold uppercase tracking-wider ${cap.howColor}`}>
                    {cap.howLabel}
                  </p>
                  <div className="space-y-1.5">
                    {cap.instructions.map((instruction, i) => (
                      <p key={i} className="text-sm leading-relaxed text-slate-600">
                        {cap.instructions.length > 1 ? `${i + 1}. ${instruction}` : instruction}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* CTA */}
          <div className="mt-10 rounded-2xl bg-kira-600 p-8 text-center text-white shadow-xl">
            <h3 className="mb-3 text-2xl font-extrabold font-title">지금 바로 시작하세요</h3>
            <p className="mb-6 leading-relaxed text-blue-100">
              공고 검색부터 제안서 생성까지,<br />
              Kira Bot이 입찰의 모든 과정을 도와드립니다.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-base font-bold text-kira-700 hover:bg-kira-50 transition-colors shadow-lg"
            >
              <Play size={18} />
              채팅 시작하기
            </button>
          </div>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-xs text-slate-400">Kira Bot v2.0 | MS Solutions</p>
            <p className="text-xs text-slate-300 mt-1">공공조달 입찰 AI 자동화 플랫폼</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserGuide;
