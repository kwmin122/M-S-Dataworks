import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CheckCircle2, XCircle, AlertCircle, Sparkles, FileText, BarChart3, ClipboardList, CalendarDays, Presentation, FolderOpen } from 'lucide-react';
import type { AnalysisResultMessage, MessageAction, OpinionMode } from '../../../types';

interface Props {
  message: AnalysisResultMessage;
  onAction?: (action: MessageAction) => void;
}

const modeLabel: Record<OpinionMode, string> = {
  conservative: '보수적',
  balanced: '균형',
  aggressive: '공격적',
};

type Tab = 'rfp_summary' | 'go_nogo';

const AnalysisResultView: React.FC<Props> = ({ message, onAction }) => {
  const { analysis } = message;
  const matching = analysis.matching;
  const a = analysis.analysis;
  const rfpSummary = a?.rfp_summary || '';
  const [opinionMode, setOpinionMode] = useState<OpinionMode>(message.opinionMode);
  const [activeTab, setActiveTab] = useState<Tab>('rfp_summary');

  const selectedOpinion = useMemo(() => {
    if (!matching?.assistant_opinions) return null;
    const opinions = matching.assistant_opinions;
    if (opinions[opinionMode]) return opinions[opinionMode];
    const prefixed = Object.entries(opinions).find(([key]) => key.startsWith(opinionMode));
    if (prefixed) return prefixed[1];
    return opinions.balanced || Object.values(opinions)[0] || null;
  }, [opinionMode, matching]);

  // 탭 헤더 렌더링
  const renderTabs = () => {
    const tabs: { key: Tab; label: string; icon: React.ReactNode; show: boolean }[] = [
      { key: 'rfp_summary', label: 'RFP 요약', icon: <FileText size={14} />, show: true },
      { key: 'go_nogo', label: matching ? 'GO/NO-GO 분석' : '자격요건', icon: <BarChart3 size={14} />, show: true },
    ];

    return (
      <div className="flex gap-1 border-b border-slate-200 mb-3">
        {tabs.filter(t => t.show).map(t => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActiveTab(t.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
              activeTab === t.key
                ? 'border-kira-600 text-kira-700'
                : 'border-transparent text-slate-400 hover:text-slate-600'
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>
    );
  };

  // RFP 요약 탭
  const renderRfpSummary = () => {
    if (!rfpSummary) {
      return <p className="text-sm text-slate-500">RFP 요약을 생성할 수 없었습니다.</p>;
    }
    return (
      <div className="prose prose-sm prose-slate max-w-none [&_table]:text-xs [&_table]:border-collapse [&_th]:bg-slate-50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:border [&_th]:border-slate-200 [&_td]:px-2 [&_td]:py-1 [&_td]:border [&_td]:border-slate-200 [&_h3]:text-sm [&_h3]:font-bold [&_h3]:text-slate-800 [&_h3]:mt-3 [&_h3]:mb-1.5 [&_li]:text-xs [&_li]:text-slate-700 [&_p]:text-xs [&_p]:text-slate-700 [&_strong]:text-slate-800 max-h-[500px] overflow-y-auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{rfpSummary}</ReactMarkdown>
      </div>
    );
  };

  // GO/NO-GO 또는 자격요건 탭
  const renderGoNoGo = () => {
    if (!matching) {
      // 회사 문서 미등록 — 자격요건만 표시
      const requirements = a?.requirements || [];
      const evalCriteria = a?.evaluation_criteria || [];
      return (
        <div className="space-y-3">
          {requirements.length > 0 ? (
            <div>
              <p className="text-xs font-semibold text-slate-600 mb-1.5">입찰참가자격 ({requirements.length}건)</p>
              <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
                {requirements.map((r, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-xs">
                    <AlertCircle size={14} className={`mt-0.5 shrink-0 ${r.is_mandatory ? 'text-red-500' : 'text-blue-500'}`} />
                    <div>
                      {r.category && <span className="font-medium text-slate-500">[{r.category}] </span>}
                      <span className="text-slate-700">{r.description}</span>
                      {r.detail && <p className="mt-0.5 text-slate-400">{r.detail}</p>}
                      {r.is_mandatory && <span className="ml-1 text-[10px] text-red-400">필수</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">추출된 자격요건이 없습니다.</p>
          )}
          {evalCriteria.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-600 mb-1.5">평가기준</p>
              <div className="space-y-1 max-h-[200px] overflow-y-auto">
                {evalCriteria.map((e, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-xs">
                    <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-600">{e.score}점</span>
                    <div>
                      {e.category && <span className="font-medium text-slate-500">[{e.category}] </span>}
                      <span className="text-slate-700">{e.item}</span>
                      {e.detail && <p className="mt-0.5 text-slate-400">{e.detail}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="rounded-lg bg-blue-50 border border-blue-200 px-3 py-2">
            <p className="text-xs text-blue-700">
              회사 문서를 등록하면 GO/NO-GO 판정과 맞춤 매칭 분석을 받을 수 있어요.
            </p>
          </div>
        </div>
      );
    }

    // 회사 문서 등록됨 — GO/NO-GO 전체 표시
    const score = Math.round(matching.overall_score || 0);
    const isGo = matching.recommendation?.toLowerCase().includes('go') &&
      !matching.recommendation?.toLowerCase().includes('no-go');

    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <span className={`rounded-full px-3 py-1 text-sm font-bold ${isGo ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {isGo ? 'GO' : 'NO-GO'}
          </span>
          <span className="text-lg font-bold text-slate-800">{score}%</span>
          <span className="text-sm text-slate-500">적합도</span>
        </div>

        {matching.summary && (
          <p className="text-sm text-slate-600 leading-relaxed">{matching.summary}</p>
        )}

        <div className="flex gap-4 text-xs">
          <span className="flex items-center gap-1 text-emerald-600"><CheckCircle2 size={14} /> 충족 {matching.met_count}</span>
          <span className="flex items-center gap-1 text-amber-600"><AlertCircle size={14} /> 부분 {matching.partially_met_count}</span>
          <span className="flex items-center gap-1 text-red-500"><XCircle size={14} /> 미충족 {matching.not_met_count}</span>
        </div>

        {matching.matches && matching.matches.length > 0 && (
          <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
            {matching.matches.map((m, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs">
                {m.status_code === 'MET' && <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-600" />}
                {m.status_code === 'PARTIALLY_MET' && <AlertCircle size={14} className="mt-0.5 shrink-0 text-amber-500" />}
                {m.status_code === 'NOT_MET' && <XCircle size={14} className="mt-0.5 shrink-0 text-red-500" />}
                {m.status_code === 'UNKNOWN' && <AlertCircle size={14} className="mt-0.5 shrink-0 text-slate-400" />}
                <div>
                  <span className="font-medium text-slate-700">{m.description}</span>
                  {m.evidence && <p className="mt-0.5 text-slate-500">{m.evidence}</p>}
                </div>
              </div>
            ))}
          </div>
        )}

        <div>
          <p className="text-xs font-semibold text-slate-600 mb-1">의견 모드</p>
          <div className="flex gap-2">
            {(Object.keys(matching.assistant_opinions || {}) as OpinionMode[])
              .filter((mode, index, arr) => arr.indexOf(mode) === index)
              .map((mode) => (
                <button key={mode} type="button"
                  className={`rounded-full border px-3 py-0.5 text-xs font-medium ${
                    opinionMode === mode ? 'border-kira-700 bg-kira-700 text-white' : 'border-slate-300 bg-white text-slate-600 hover:border-kira-300'
                  }`}
                  onClick={() => setOpinionMode(mode)}
                >{modeLabel[mode] || mode}</button>
              ))}
          </div>
        </div>

        {selectedOpinion?.actions?.length ? (
          <div>
            <p className="text-xs font-semibold text-slate-600 mb-1">추천 준비사항</p>
            <ul className="space-y-1">
              {selectedOpinion.actions.slice(0, 5).map((action, idx) => (
                <li key={idx} className="flex items-start gap-1.5 text-xs text-slate-600">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                  <span>{action}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {selectedOpinion?.risk_notes?.length ? (
          <div>
            <p className="text-xs font-semibold text-slate-600 mb-1">리스크 참고사항</p>
            <ul className="space-y-1">
              {selectedOpinion.risk_notes.map((note, idx) => (
                <li key={idx} className="flex items-start gap-1.5 text-xs text-slate-500">
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="mt-1 flex gap-2">
          <button type="button"
            onClick={() => onAction?.({ type: 'generate_proposal_v2', bidTitle: a?.title || '', format: 'docx' })}
            className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-kira-600 to-kira-700 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:from-kira-700 hover:to-kira-800 transition-all"
          >
            <Sparkles size={14} />
            제안서 생성 (DOCX)
          </button>
          <button type="button"
            onClick={() => onAction?.({ type: 'generate_proposal_v2', bidTitle: a?.title || '', format: 'hwpx' })}
            className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-700 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:from-emerald-700 hover:to-emerald-800 transition-all"
          >
            <Sparkles size={14} />
            제안서 생성 (HWPX)
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-2">
      {/* 공고 제목 */}
      {a?.title && (
        <p className="text-sm font-medium text-slate-800">{a.title}</p>
      )}
      {(a?.issuing_org || a?.budget || a?.deadline) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          {a?.issuing_org && <span>발주처: {a.issuing_org}</span>}
          {a?.budget && <span>예산: {a.budget}</span>}
          {a?.deadline && <span>마감: {a.deadline}</span>}
        </div>
      )}
      {/* 2-탭 UI */}
      {renderTabs()}
      {activeTab === 'rfp_summary' ? renderRfpSummary() : renderGoNoGo()}

      {/* 제출 체크리스트 버튼 */}
      <button type="button"
        onClick={() => onAction?.({ type: 'view_checklist' })}
        className="mt-2 flex items-center gap-1.5 rounded-lg border border-kira-200 bg-white px-3 py-1.5 text-xs font-medium text-kira-700 shadow-sm hover:bg-kira-50 transition-all"
      >
        <ClipboardList size={14} />
        제출 체크리스트
      </button>

      {/* Phase 2 문서 생성 버튼 */}
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button"
          onClick={() => onAction?.({ type: 'generate_wbs' })}
          className="flex items-center gap-1.5 rounded-lg border border-kira-200 bg-white px-3 py-1.5 text-xs font-medium text-kira-700 shadow-sm hover:bg-kira-50 transition-all"
        >
          <CalendarDays size={14} />
          수행계획서/WBS
        </button>
        <button type="button"
          onClick={() => onAction?.({ type: 'generate_ppt' })}
          className="flex items-center gap-1.5 rounded-lg border border-kira-200 bg-white px-3 py-1.5 text-xs font-medium text-kira-700 shadow-sm hover:bg-kira-50 transition-all"
        >
          <Presentation size={14} />
          PPT 발표자료
        </button>
        <button type="button"
          onClick={() => onAction?.({ type: 'generate_track_record' })}
          className="flex items-center gap-1.5 rounded-lg border border-kira-200 bg-white px-3 py-1.5 text-xs font-medium text-kira-700 shadow-sm hover:bg-kira-50 transition-all"
        >
          <FolderOpen size={14} />
          실적/경력 기술서
        </button>
      </div>
    </div>
  );
};

export default AnalysisResultView;
