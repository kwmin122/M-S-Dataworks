import React, { useState, useEffect, useCallback } from 'react';
import {
  FileText, Play, Loader2, AlertCircle, CheckCircle2,
  FileCheck, Eye, BookOpen, ChevronDown, ChevronUp, RotateCcw, History, Clock, Timer,
} from 'lucide-react';
import type {
  GenerateResult, StudioProject, CurrentRevisionData, RevisionSection, GenerateDocType,
  SlideMetadata, QnaPairData, PackageItem, GenerationPerformance,
} from '../../../services/studioApi';
import { generateProposal, getCurrentRevision, listPackageItems } from '../../../services/studioApi';
import GenerateContractView from './GenerateContractView';
import QuotaGate from '../QuotaGate';

interface GenerateStageProps {
  projectId: string;
  project: StudioProject;
  onProjectUpdate: () => void;
  onDocTypeChange?: (dt: GenerateDocType) => void;
}

type GenerationPhase = 'idle' | 'assembling_contract' | 'generating_sections' | 'saving_revision' | 'done' | 'error';

const PHASE_LABELS_BY_DOC: Record<GenerateDocType, Record<GenerationPhase, string>> = {
  proposal: { idle: '', assembling_contract: '입력 계약 조립 중...', generating_sections: '제안서 섹션 생성 중... (1~2분 소요)', saving_revision: '리비전 저장 중...', done: '완료', error: '오류 발생' },
  execution_plan: { idle: '', assembling_contract: '입력 계약 조립 중...', generating_sections: 'WBS/수행계획 생성 중... (1~2분 소요)', saving_revision: '리비전 저장 중...', done: '완료', error: '오류 발생' },
  track_record: { idle: '', assembling_contract: '입력 계약 조립 중...', generating_sections: '실적기술서 생성 중... (1~2분 소요)', saving_revision: '리비전 저장 중...', done: '완료', error: '오류 발생' },
  presentation: { idle: '', assembling_contract: '입력 계약 조립 중...', generating_sections: '슬라이드 생성 중... (1~2분 소요)', saving_revision: '리비전 저장 중...', done: '완료', error: '오류 발생' },
};

export default function GenerateStage({ projectId, project, onProjectUpdate, onDocTypeChange }: GenerateStageProps) {
  const [docType, setDocTypeInternal] = useState<GenerateDocType>('proposal');
  const setDocType = useCallback((dt: GenerateDocType) => {
    setDocTypeInternal(dt);
    onDocTypeChange?.(dt);
  }, [onDocTypeChange]);
  const [phase, setPhase] = useState<GenerationPhase>('idle');
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [error, setError] = useState('');
  const [showContract, setShowContract] = useState(false);
  const [revision, setRevision] = useState<CurrentRevisionData | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const [hasPresentationItem, setHasPresentationItem] = useState<boolean | null>(null);

  const hasSnapshot = !!project.active_analysis_snapshot_id;
  const generating = phase !== 'idle' && phase !== 'done' && phase !== 'error';

  // Load package items to check for presentation target
  useEffect(() => {
    listPackageItems(projectId)
      .then((items) => setHasPresentationItem(items.some((i) => i.generation_target === 'presentation')))
      .catch(() => setHasPresentationItem(null));
  }, [projectId]);

  // Load existing revision on mount or doc type change
  useEffect(() => {
    getCurrentRevision(projectId, docType)
      .then(setRevision)
      .catch(() => setRevision(null));
  }, [projectId, docType]);

  const handleGenerate = useCallback(async () => {
    setPhase('assembling_contract');
    setError('');
    setResult(null);
    // Keep previous revision — allows "이전 버전 보기" fallback on failure

    try {
      // Phase 1: contract assembly (immediate)
      setPhase('generating_sections');

      // Phase 2: actual generation (long-running)
      const res = await generateProposal(projectId, { doc_type: docType });

      // Phase 3: saving
      setPhase('saving_revision');
      setResult(res);
      setShowContract(true);

      // Load the revision content for preview
      try {
        const rev = await getCurrentRevision(projectId, docType);
        setRevision(rev);
        setShowPreview(true);
      } catch { /* revision load failure is non-fatal */ }

      setPhase('done');
      onProjectUpdate();
    } catch (err) {
      setPhase('error');
      setError(err instanceof Error ? err.message : '생성 중 오류가 발생했습니다');
    }
  }, [projectId, docType, onProjectUpdate]);

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">문서 생성</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            분석 결과와 회사 역량을 기반으로 문서를 생성합니다
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

      {error && <QuotaGate error={error} />}

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
          <div className="flex items-center gap-2 ml-6">
            <button
              onClick={handleGenerate}
              disabled={generating || !hasSnapshot}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              <RotateCcw size={12} />
              다시 시도
            </button>
            {revision && (
              <button
                onClick={() => { setShowPreview(true); setError(''); }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-700 border border-red-300 rounded-md hover:bg-red-100 transition-colors"
              >
                <History size={12} />
                이전 버전 보기
              </button>
            )}
          </div>
        </div>
      )}

      {/* Doc type selector */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-sm text-slate-600">생성 대상:</span>
        {([['proposal', '기술 제안서'], ['execution_plan', '수행계획서/WBS'], ['track_record', '실적기술서'], ['presentation', '발표자료(PPT)']] as const).map(([key, label]) => {
          const isPptDisabled = key === 'presentation' && hasPresentationItem === false;
          return (
            <button
              key={key}
              onClick={() => { if (!isPptDisabled) { setDocType(key); setResult(null); } }}
              disabled={isPptDisabled}
              title={isPptDisabled ? '발표평가 미포함 — 패키지 단계에서 발표자료를 추가해주세요' : undefined}
              className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                isPptDisabled
                  ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                  : docType === key
                    ? 'bg-kira-600 text-white border-kira-600'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              {label}
              {isPptDisabled && <span className="ml-1 text-xs">(미포함)</span>}
            </button>
          );
        })}
      </div>

      {/* Generate button + controls */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={handleGenerate}
          disabled={generating || !hasSnapshot}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? (
            <><Loader2 size={16} className="animate-spin" /> {PHASE_LABELS_BY_DOC[docType][phase]}</>
          ) : (
            <><Play size={16} /> {{ proposal: '제안서 생성', execution_plan: '수행계획서 생성', track_record: '실적기술서 생성', presentation: '발표자료 생성' }[docType]}</>
          )}
        </button>
        <button
          onClick={() => setShowContract(!showContract)}
          className="flex items-center gap-1.5 px-3 py-2 text-sm text-slate-600 hover:text-slate-800 border border-slate-200 rounded-lg hover:bg-slate-50"
        >
          <Eye size={14} />
          입력 계약 {showContract ? '닫기' : '보기'}
        </button>
        {revision && (
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-slate-600 hover:text-slate-800 border border-slate-200 rounded-lg hover:bg-slate-50"
          >
            <BookOpen size={14} />
            미리보기 {showPreview ? '닫기' : '열기'}
          </button>
        )}
      </div>

      {/* Generation contract view */}
      {showContract && (
        <GenerateContractView
          project={project}
          contract={result?.generation_contract ?? null}
        />
      )}

      {/* Result summary */}
      {result && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 mb-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 size={18} className="text-green-600" />
            <h3 className="text-sm font-semibold text-green-800">생성 완료</h3>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="text-slate-600">상태: <span className="font-medium text-green-700">{result.status}</span></div>
            {docType === 'presentation' ? (
              <div className="text-slate-600">슬라이드: <span className="font-medium">{result.generation_contract?.target_slide_count ?? result.sections_count}장</span></div>
            ) : (
              <div className="text-slate-600">섹션 수: <span className="font-medium">{result.sections_count}</span></div>
            )}
            {result.generation_time_sec && (
              <div className="text-slate-600">소요 시간: <span className="font-medium">{result.generation_time_sec.toFixed(1)}초</span></div>
            )}
          </div>
          {result.performance && (
            <PerformanceBadge performance={result.performance} />
          )}
          <div className="mt-3 flex items-center gap-2">
            <FileCheck size={14} className="text-green-600" />
            <span className="text-xs text-green-700">
              Run: {result.run_id.slice(0, 8)}... / Revision: {result.revision_id.slice(0, 8)}...
            </span>
          </div>
          {docType === 'presentation' && (
            <a
              href={`${import.meta.env.VITE_API_BASE_URL || (typeof window !== 'undefined' && window.location.port === '5173' ? 'http://localhost:8000' : '')}/api/studio/projects/${projectId}/documents/presentation/download`}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-kira-600 border border-kira-200 rounded-lg hover:bg-kira-50"
              download
            >
              <FileCheck size={14} />
              .pptx 다운로드
            </a>
          )}
        </div>
      )}

      {/* Quality Report */}
      {revision?.quality_report && (
        <QualityReportView report={revision.quality_report as QualityReportData} />
      )}

      {/* Revision preview */}
      {showPreview && revision && (
        <RevisionPreview revision={revision} />
      )}
    </div>
  );
}


interface QualityDimensionData {
  name: string;
  label: string;
  score: number;
  status: 'pass' | 'warn' | 'fail';
  details: string[];
}

interface QualityReportData {
  overall_score?: number;
  grade?: string;
  recommendation?: string;
  pass_count?: number;
  warn_count?: number;
  fail_count?: number;
  dimensions?: QualityDimensionData[];
}

function QualityReportView({ report }: { report: QualityReportData }) {
  const [expanded, setExpanded] = useState(false);
  if (!report.overall_score && !report.dimensions) return null;

  const gradeColor = {
    '수': 'text-green-700 bg-green-50 border-green-200',
    '우': 'text-blue-700 bg-blue-50 border-blue-200',
    '미': 'text-amber-700 bg-amber-50 border-amber-200',
    '양': 'text-orange-700 bg-orange-50 border-orange-200',
    '가': 'text-red-700 bg-red-50 border-red-200',
  }[report.grade || '미'] || 'text-slate-700 bg-slate-50 border-slate-200';

  const statusIcon = (s: string) => s === 'pass' ? '✓' : s === 'warn' ? '!' : '✗';
  const statusColor = (s: string) => s === 'pass' ? 'text-green-600' : s === 'warn' ? 'text-amber-600' : 'text-red-600';

  return (
    <div className={`rounded-xl border p-4 mb-4 ${gradeColor}`}>
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold">{report.grade || '-'}</span>
          <span className="text-sm font-medium">{report.overall_score?.toFixed(1)}점</span>
          <span className="text-xs opacity-70">
            {report.pass_count || 0}통과 / {report.warn_count || 0}주의 / {report.fail_count || 0}미달
          </span>
        </div>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {expanded && report.dimensions && (
        <div className="mt-3 space-y-2">
          {report.dimensions.map((d) => (
            <div key={d.name} className="flex items-center gap-2 text-xs">
              <span className={`font-bold ${statusColor(d.status)}`}>{statusIcon(d.status)}</span>
              <span className="font-medium w-24">{d.label}</span>
              <div className="flex-1 h-1.5 rounded-full bg-white/50 overflow-hidden">
                <div
                  className={`h-full rounded-full ${d.status === 'pass' ? 'bg-green-500' : d.status === 'warn' ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${d.score * 100}%` }}
                />
              </div>
              <span className="w-10 text-right">{(d.score * 100).toFixed(0)}%</span>
            </div>
          ))}
          {report.recommendation && (
            <p className="text-xs mt-2 pt-2 border-t border-current/10">{report.recommendation}</p>
          )}
        </div>
      )}
    </div>
  );
}


function RevisionPreview({ revision }: { revision: CurrentRevisionData }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(0);
  const isTrackRecord = revision.doc_type === 'track_record' || ((revision.records?.length ?? 0) > 0 && revision.sections.length === 0);
  const isPresentation = revision.doc_type === 'presentation' || ((revision.slides?.length ?? 0) > 0);
  const hasContent = revision.sections.length > 0 || (revision.records?.length ?? 0) > 0 || (revision.personnel?.length ?? 0) > 0 || (revision.slides?.length ?? 0) > 0;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <BookOpen size={16} className="text-slate-600" />
        <h3 className="text-sm font-semibold text-slate-700">
          {revision.title || '문서'} — 리비전 #{revision.revision_number}
        </h3>
        <span className="text-xs text-slate-400">{revision.source === 'ai_generated' ? 'AI 생성' : revision.source}</span>
      </div>

      {!hasContent ? (
        <p className="text-sm text-slate-400">내용이 없습니다.</p>
      ) : isPresentation ? (
        <PresentationPreview
          slides={revision.slides ?? []}
          qnaPairs={revision.qna_pairs ?? []}
          slideCount={revision.slide_count}
          durationMin={revision.total_duration_min}
        />
      ) : isTrackRecord ? (
        <TrackRecordPreview records={revision.records ?? []} personnel={revision.personnel ?? []} />
      ) : (
        <div className="space-y-1">
          {revision.sections.map((section, idx) => (
            <div key={idx} className="border border-slate-100 rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-50 text-sm"
              >
                <span className="font-medium text-slate-700">{section.name}</span>
                {expandedIdx === idx
                  ? <ChevronUp size={14} className="text-slate-400" />
                  : <ChevronDown size={14} className="text-slate-400" />
                }
              </button>
              {expandedIdx === idx && (
                <div className="px-3 pb-3 text-sm text-slate-600 whitespace-pre-wrap border-t border-slate-100">
                  {section.text}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TrackRecordPreview({
  records,
  personnel,
}: {
  records: Array<{ project_name: string; description: string; relevance_score?: number }>;
  personnel: Array<{ name: string; role: string; match_reason?: string }>;
}) {
  return (
    <div className="space-y-4">
      {records.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">수행실적 ({records.length}건)</h4>
          <div className="space-y-2">
            {records.map((r, i) => (
              <div key={i} className="rounded-lg border border-slate-100 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-slate-800">{r.project_name}</span>
                  {r.relevance_score != null && (
                    <span className="text-xs text-kira-600">관련도 {Math.round(r.relevance_score * 100)}%</span>
                  )}
                </div>
                <p className="text-xs text-slate-500 line-clamp-2">{r.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      {personnel.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">투입인력 ({personnel.length}명)</h4>
          <div className="space-y-2">
            {personnel.map((p, i) => (
              <div key={i} className="rounded-lg border border-slate-100 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-slate-800">{p.name}</span>
                  <span className="text-xs text-slate-400">{p.role}</span>
                </div>
                {p.match_reason && <p className="text-xs text-slate-500">{p.match_reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function PresentationPreview({
  slides,
  qnaPairs,
  slideCount,
  durationMin,
}: {
  slides: SlideMetadata[];
  qnaPairs: QnaPairData[];
  slideCount?: number;
  durationMin?: number;
}) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex gap-4 text-xs text-slate-500">
        {slideCount != null && <span>슬라이드 {slideCount}장</span>}
        {durationMin != null && <span>발표 {durationMin}분</span>}
        {qnaPairs.length > 0 && <span>예상 Q&A {qnaPairs.length}건</span>}
      </div>

      {/* Slide list */}
      {slides.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">슬라이드 구성</h4>
          <div className="space-y-1">
            {slides.map((slide, i) => (
              <div key={i} className="flex items-center gap-2 rounded-lg border border-slate-100 px-3 py-2">
                <span className="text-xs text-slate-400 w-6">{i + 1}</span>
                <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">{slide.slide_type}</span>
                <span className="text-sm text-slate-700">{slide.title}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Q&A */}
      {qnaPairs.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">예상 질의응답</h4>
          <div className="space-y-2">
            {qnaPairs.map((qa, i) => (
              <div key={i} className="rounded-lg border border-slate-100 p-3">
                <p className="text-sm font-medium text-slate-700 mb-1">Q: {qa.question}</p>
                <p className="text-xs text-slate-500">A: {qa.answer}</p>
                {qa.category && <span className="text-xs text-slate-400 mt-1 inline-block">#{qa.category}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function formatDuration(sec: number): string {
  const min = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  if (min === 0) return `${s}초`;
  return `${min}분 ${s}초`;
}

function PerformanceBadge({ performance }: { performance: GenerationPerformance }) {
  const { duration_sec, target_sec, within_target, timed_out } = performance;
  const targetLabel = formatDuration(target_sec);

  if (timed_out) {
    return (
      <div className="mt-2 flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-1.5">
        <Timer size={14} className="text-red-500" />
        <span className="text-xs font-medium text-red-700">
          타임아웃 ({formatDuration(duration_sec)}, 제한 5분 초과)
        </span>
      </div>
    );
  }

  if (within_target) {
    return (
      <div className="mt-2 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-3 py-1.5">
        <Clock size={14} className="text-green-500" />
        <span className="text-xs font-medium text-green-700">
          {formatDuration(duration_sec)} (목표 {targetLabel} 이내)
        </span>
      </div>
    );
  }

  return (
    <div className="mt-2 flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-1.5">
      <Clock size={14} className="text-amber-500" />
      <span className="text-xs font-medium text-amber-700">
        {formatDuration(duration_sec)} (목표 {targetLabel} 초과)
      </span>
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
