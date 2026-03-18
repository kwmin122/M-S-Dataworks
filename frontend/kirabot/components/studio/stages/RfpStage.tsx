import React, { useState } from 'react';
import { FileText, Search, Upload, Loader2, CheckCircle2 } from 'lucide-react';
import Button from '../../Button';
import type { StudioProject } from '../../../services/studioApi';

interface RfpStageProps {
  project: StudioProject;
  onAnalyze: (text: string) => Promise<void>;
  onClassify: () => Promise<void>;
}

export default function RfpStage({ project, onAnalyze, onClassify }: RfpStageProps) {
  const [rfpText, setRfpText] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [error, setError] = useState('');

  const hasSnapshot = !!project.active_analysis_snapshot_id;

  const handleAnalyze = async () => {
    if (rfpText.trim().length < 50) {
      setError('공고 내용을 50자 이상 입력해주세요.');
      return;
    }
    setAnalyzing(true);
    setError('');
    try {
      await onAnalyze(rfpText);
      setRfpText(''); // Clear after success
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'RFP 분석 실패';
      setError(msg);
    } finally {
      setAnalyzing(false);
    }
  };

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
        입찰 공고를 입력하면 자동으로 분석하고 제출 패키지를 분류합니다.
      </p>

      {/* Snapshot status */}
      {hasSnapshot && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 mb-6">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 size={18} className="text-green-600" />
            <span className="text-sm font-semibold text-green-800">분석 완료</span>
          </div>
          <p className="text-xs text-green-700 ml-6">
            분석 스냅샷이 연결되어 있습니다. 제출 패키지 분류를 실행하거나, 새로운 공고를 다시 분석할 수 있습니다.
          </p>
        </div>
      )}

      {/* Text input */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-700 mb-2">
          공고 내용 입력
        </label>
        <textarea
          value={rfpText}
          onChange={(e) => setRfpText(e.target.value)}
          placeholder="공고문 전문 또는 주요 내용을 붙여넣기 해주세요. (최소 50자)"
          className="w-full h-48 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-kira-500 focus:border-transparent resize-y"
          disabled={analyzing}
        />
        <div className="flex justify-between mt-1.5">
          <span className="text-xs text-slate-400">
            {rfpText.length}자
          </span>
          <Button onClick={handleAnalyze} size="sm" disabled={analyzing || rfpText.trim().length < 50}>
            {analyzing ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span className="ml-1">분석 중...</span>
              </>
            ) : (
              '공고 분석'
            )}
          </Button>
        </div>
      </div>

      {/* Future input methods */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <button
          disabled
          className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 opacity-50 cursor-not-allowed"
        >
          <Search size={16} className="text-slate-400" />
          <span className="text-xs text-slate-500">나라장터 검색 (준비 중)</span>
        </button>
        <button
          disabled
          className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 opacity-50 cursor-not-allowed"
        >
          <Upload size={16} className="text-slate-400" />
          <span className="text-xs text-slate-500">파일 업로드 (준비 중)</span>
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Classify action */}
      {hasSnapshot && (
        <Button onClick={handleClassify} disabled={classifying} size="sm" variant="secondary">
          {classifying ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              <span className="ml-1">분류 중...</span>
            </>
          ) : (
            '제출 패키지 분류 실행'
          )}
        </Button>
      )}
    </div>
  );
}
