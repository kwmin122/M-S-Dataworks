import React from 'react';
import { PenTool, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function StudioHome() {
  const navigate = useNavigate();

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-kira-50">
          <PenTool size={32} className="text-kira-500" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">입찰 문서 AI 작성</h1>
        <p className="mt-3 text-base text-slate-500 leading-relaxed">
          공고, 회사 역량, 스타일을 학습시켜<br />
          제안서, 수행계획서, PPT, 실적기술서를<br />
          자동 생성하고 개선하는 전문가용 워크스페이스입니다.
        </p>
        <div className="mt-8 inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-kira-50 text-kira-700 text-sm font-semibold">
          곧 오픈 예정
        </div>
        <div className="mt-6">
          <button
            onClick={() => navigate('/chat')}
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 transition-colors"
          >
            <ArrowLeft size={16} />
            공고 탐색으로 돌아가기
          </button>
        </div>
      </div>
    </div>
  );
}
