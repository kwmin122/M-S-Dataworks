import React from 'react';
import { ArrowLeft, Play, AlertCircle, CheckCircle2, Sparkles } from 'lucide-react';
import KiraBotLogo from '../KiraBotLogo';
import { useActiveConversation } from '../../hooks/useActiveConversation';

interface UserGuideProps {
  onClose: () => void;
}

const UserGuide: React.FC<UserGuideProps> = ({ onClose }) => {
  const { conversation } = useActiveConversation();
  const hasCompanyProfile = Boolean(conversation?.companyProfile?.companyName);
  const companyChunks = conversation?.companyChunks || 0;

  return (
    <div className="flex h-full flex-col bg-gradient-to-b from-slate-50 to-white">
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
        <h2 className="text-sm font-bold text-slate-800">Kira Bot 사용 가이드</h2>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 py-12">
          {/* Hero */}
          <div className="mb-16 text-center">
            <div className="mb-6 flex justify-center">
              <div className="rounded-full bg-gradient-to-br from-kira-500 to-kira-700 p-4 shadow-lg">
                <KiraBotLogo size={72} className="text-white" />
              </div>
            </div>
            <h1 className="mb-4 text-4xl font-bold text-slate-800">
              Kira Bot과 함께하는<br />입찰 성공 여정
            </h1>
            <p className="text-lg text-slate-600">
              공고 검색부터 제안서 생성까지, AI가 모든 과정을 자동화합니다.
            </p>
          </div>

          {/* Current Status Card */}
          {hasCompanyProfile ? (
            <div className="mb-12 rounded-xl border border-green-200 bg-green-50 p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-green-100">
                  <CheckCircle2 size={24} className="text-green-600" />
                </div>
                <div className="flex-1">
                  <h3 className="mb-2 text-lg font-bold text-green-900">
                    회사 정보가 등록되었습니다! 🎉
                  </h3>
                  <p className="mb-3 text-sm text-green-700">
                    <strong>{conversation.companyProfile.companyName}</strong> — {companyChunks}개 문서 등록됨
                  </p>
                  <p className="text-sm text-green-600">
                    이제 공고를 분석하면 <strong>GO/NO-GO 자동 판단</strong>과 <strong>맞춤형 제안서 생성</strong>이 가능합니다.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="mb-12 rounded-xl border border-amber-200 bg-amber-50 p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-amber-100">
                  <AlertCircle size={24} className="text-amber-600" />
                </div>
                <div className="flex-1">
                  <h3 className="mb-2 text-lg font-bold text-amber-900">
                    먼저 회사 정보를 등록하세요
                  </h3>
                  <p className="mb-4 text-sm text-amber-700">
                    회사 소개서, 실적, 인력 정보를 등록하면 GO/NO-GO 판단과 제안서 품질이 크게 향상됩니다.
                  </p>
                  <button
                    type="button"
                    onClick={onClose}
                    className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 transition-colors"
                  >
                    채팅에서 "회사 역량 DB 구축" 시작하기
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 3-Step Process */}
          <section className="mb-12">
            <h2 className="mb-6 flex items-center gap-2 text-2xl font-bold text-slate-800">
              <Sparkles size={24} className="text-kira-600" />
              3단계로 끝내는 입찰 준비
            </h2>
            <div className="space-y-4">
              {/* Step 1 */}
              <div className="group relative overflow-hidden rounded-xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md transition-all">
                <div className="absolute left-0 top-0 h-full w-1.5 bg-gradient-to-b from-kira-500 to-kira-700"></div>
                <div className="flex items-start gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-kira-100 text-lg font-bold text-kira-700">
                    1
                  </div>
                  <div className="flex-1">
                    <h3 className="mb-2 text-lg font-semibold text-slate-800">
                      공고 찾기 & 분석
                    </h3>
                    <p className="mb-3 text-sm text-slate-600">
                      키워드로 공고를 검색하거나 파일을 업로드하면, AI가 자격요건을 자동으로 추출하고 RFP를 요약합니다.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        나라장터 검색
                      </span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        PDF/HWP 업로드
                      </span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        RFP 자동 요약
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Step 2 */}
              <div className="group relative overflow-hidden rounded-xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md transition-all">
                <div className="absolute left-0 top-0 h-full w-1.5 bg-gradient-to-b from-emerald-500 to-emerald-700"></div>
                <div className="flex items-start gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-lg font-bold text-emerald-700">
                    2
                  </div>
                  <div className="flex-1">
                    <h3 className="mb-2 text-lg font-semibold text-slate-800">
                      GO/NO-GO 자동 판단
                    </h3>
                    <p className="mb-3 text-sm text-slate-600">
                      회사 역량 DB와 공고 요건을 AI가 자동 매칭하여 입찰 적합성을 즉시 판단합니다.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        자격요건 매칭
                      </span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        적합성 점수
                      </span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        준비 가이드
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Step 3 */}
              <div className="group relative overflow-hidden rounded-xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md transition-all">
                <div className="absolute left-0 top-0 h-full w-1.5 bg-gradient-to-b from-purple-500 to-purple-700"></div>
                <div className="flex items-start gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-purple-100 text-lg font-bold text-purple-700">
                    3
                  </div>
                  <div className="flex-1">
                    <h3 className="mb-2 text-lg font-semibold text-slate-800">
                      제안서 자동 생성
                    </h3>
                    <p className="mb-3 text-sm text-slate-600">
                      클릭 한 번으로 제안서, WBS, PPT를 자동 생성하고 즉시 다운로드합니다.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        제안서 DOCX
                      </span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        수행계획서 XLSX
                      </span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        발표자료 PPTX
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* CTA */}
          <div className="rounded-2xl bg-gradient-to-br from-kira-600 to-kira-800 p-8 text-center text-white shadow-xl">
            <h3 className="mb-3 text-2xl font-bold">지금 바로 시작하세요</h3>
            <p className="mb-6 text-kira-100">
              채팅창에 공고 키워드를 입력하거나 파일을 업로드하면 모든 과정이 자동으로 시작됩니다.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3 text-base font-semibold text-kira-700 hover:bg-kira-50 transition-colors shadow-lg"
            >
              <Play size={18} />
              채팅 시작하기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserGuide;
