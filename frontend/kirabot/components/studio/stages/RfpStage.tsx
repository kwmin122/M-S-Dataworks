import React, { useState } from 'react';
import { FileText, Search, Upload, Loader2, CheckCircle2 } from 'lucide-react';
import Button from '../../Button';
import type { StudioProject } from '../../../services/studioApi';

interface RfpStageProps {
  project: StudioProject;
  onClassify: () => Promise<void>;
}

export default function RfpStage({ project, onClassify }: RfpStageProps) {
  const [classifying, setClassifying] = useState(false);
  const [error, setError] = useState('');

  const hasSnapshot = !!project.active_analysis_snapshot_id;

  const handleClassify = async () => {
    setClassifying(true);
    setError('');
    try {
      await onClassify();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '패키지 분류 실패';
      setError(msg);
    } finally {
      setClassifying(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <h2 className="text-lg font-bold text-slate-900 mb-1">공고 분석</h2>
      <p className="text-sm text-slate-500 mb-6">
        입찰 공고를 입력하면 제출 패키지를 자동으로 분류합니다.
      </p>

      {/* Snapshot status */}
      {hasSnapshot ? (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 mb-6">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 size={18} className="text-green-600" />
            <span className="text-sm font-semibold text-green-800">분석 완료</span>
          </div>
          <p className="text-xs text-green-700 ml-6">
            분석 스냅샷이 연결되어 있습니다. 제출 패키지 분류를 실행할 수 있습니다.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border-2 border-dashed border-slate-200 p-8 mb-6">
          <div className="text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100">
              <Upload size={24} className="text-slate-400" />
            </div>
            <p className="text-sm font-medium text-slate-700 mb-1">공고 문서를 분석해주세요</p>
            <p className="text-xs text-slate-400 leading-relaxed">
              채팅에서 공고를 분석한 후 Studio로 가져오거나,<br />
              프로젝트 생성 시 분석 스냅샷을 연결해주세요.
            </p>
          </div>
        </div>
      )}

      {/* Input methods (placeholder for future) */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <button
          disabled
          className="flex flex-col items-center gap-2 rounded-xl border border-slate-200 bg-white p-4 opacity-50 cursor-not-allowed"
        >
          <Search size={20} className="text-slate-400" />
          <span className="text-xs text-slate-500">나라장터 검색</span>
        </button>
        <button
          disabled
          className="flex flex-col items-center gap-2 rounded-xl border border-slate-200 bg-white p-4 opacity-50 cursor-not-allowed"
        >
          <Upload size={20} className="text-slate-400" />
          <span className="text-xs text-slate-500">문서 업로드</span>
        </button>
        <button
          disabled
          className="flex flex-col items-center gap-2 rounded-xl border border-slate-200 bg-white p-4 opacity-50 cursor-not-allowed"
        >
          <FileText size={20} className="text-slate-400" />
          <span className="text-xs text-slate-500">텍스트 입력</span>
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Classify action */}
      {hasSnapshot && (
        <Button onClick={handleClassify} disabled={classifying} size="sm">
          {classifying ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              <span className="ml-1.5">분류 중...</span>
            </>
          ) : (
            '제출 패키지 분류 실행'
          )}
        </Button>
      )}
    </div>
  );
}
