import React, { useState, useCallback } from 'react';
import {
  FileText, Play, Loader2, AlertCircle, CheckCircle2,
  FileCheck, Eye,
} from 'lucide-react';
import type { GenerateResult, GenerationContract, StudioProject } from '../../../services/studioApi';
import { generateProposal } from '../../../services/studioApi';
import GenerateContractView from './GenerateContractView';

interface GenerateStageProps {
  projectId: string;
  project: StudioProject;
  onProjectUpdate: () => void;
}

export default function GenerateStage({ projectId, project, onProjectUpdate }: GenerateStageProps) {
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [error, setError] = useState('');
  const [showContract, setShowContract] = useState(false);

  const hasSnapshot = !!project.active_analysis_snapshot_id;

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError('');
    setResult(null);
    try {
      const res = await generateProposal(projectId);
      setResult(res);
      setShowContract(true); // Auto-show contract after generation
      onProjectUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : '생성 중 오류가 발생했습니다');
    } finally {
      setGenerating(false);
    }
  }, [projectId, onProjectUpdate]);

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">문서 생성</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            분석 결과와 회사 역량을 기반으로 제안서를 생성합니다
          </p>
        </div>
      </div>

      {/* Pre-conditions check */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">생성 조건</h3>
        <div className="space-y-2">
          <ConditionRow
            label="공고 분석 완료"
            met={hasSnapshot}
            detail={hasSnapshot ? '스냅샷 연결됨' : '공고 단계에서 분석을 먼저 실행해주세요'}
          />
          <ConditionRow
            label="회사 역량"
            met={true}
            detail="회사 자산이 없어도 생성 가능 (범용 지식 기반)"
          />
          <ConditionRow
            label="스타일 핀"
            met={!!project.pinned_style_skill_id}
            detail={project.pinned_style_skill_id ? '스타일 핀 설정됨' : '스타일 없이 기본 문체로 생성'}
            optional
          />
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 mb-4 flex items-center gap-2">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Generate button */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={handleGenerate}
          disabled={generating || !hasSnapshot}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? (
            <><Loader2 size={16} className="animate-spin" /> 생성 중...</>
          ) : (
            <><Play size={16} /> 제안서 생성</>
          )}
        </button>
        <button
          onClick={() => setShowContract(!showContract)}
          className="flex items-center gap-1.5 px-3 py-2 text-sm text-slate-600 hover:text-slate-800 border border-slate-200 rounded-lg hover:bg-slate-50"
        >
          <Eye size={14} />
          입력 계약 {showContract ? '닫기' : '보기'}
        </button>
      </div>

      {/* Generation contract view — shows actual contract after generation, expected before */}
      {showContract && (
        <GenerateContractView
          project={project}
          contract={result?.generation_contract ?? null}
        />
      )}

      {/* Result */}
      {result && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 size={18} className="text-green-600" />
            <h3 className="text-sm font-semibold text-green-800">생성 완료</h3>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="text-slate-600">상태: <span className="font-medium text-green-700">{result.status}</span></div>
            <div className="text-slate-600">섹션 수: <span className="font-medium">{result.sections_count}</span></div>
            {result.generation_time_sec && (
              <div className="text-slate-600">소요 시간: <span className="font-medium">{result.generation_time_sec.toFixed(1)}초</span></div>
            )}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <FileCheck size={14} className="text-green-600" />
            <span className="text-xs text-green-700">Run: {result.run_id.slice(0, 8)}... / Revision: {result.revision_id.slice(0, 8)}...</span>
          </div>
        </div>
      )}
    </div>
  );
}


function ConditionRow({
  label,
  met,
  detail,
  optional,
}: {
  label: string;
  met: boolean;
  detail: string;
  optional?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      {met ? (
        <CheckCircle2 size={14} className="text-green-500 shrink-0" />
      ) : optional ? (
        <FileText size={14} className="text-slate-400 shrink-0" />
      ) : (
        <AlertCircle size={14} className="text-red-400 shrink-0" />
      )}
      <span className="text-sm text-slate-700">{label}</span>
      <span className="text-xs text-slate-400">— {detail}</span>
    </div>
  );
}
