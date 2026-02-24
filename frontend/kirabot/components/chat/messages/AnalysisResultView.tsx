import React, { useMemo, useState } from 'react';
import { CheckCircle2, XCircle, AlertCircle, Sparkles } from 'lucide-react';
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

const AnalysisResultView: React.FC<Props> = ({ message, onAction }) => {
  const { analysis } = message;
  const matching = analysis.matching;
  const [opinionMode, setOpinionMode] = useState<OpinionMode>(message.opinionMode);

  const selectedOpinion = useMemo(() => {
    if (!matching?.assistant_opinions) return null;
    const opinions = matching.assistant_opinions;
    if (opinions[opinionMode]) return opinions[opinionMode];
    const prefixed = Object.entries(opinions).find(([key]) => key.startsWith(opinionMode));
    if (prefixed) return prefixed[1];
    return opinions.balanced || Object.values(opinions)[0] || null;
  }, [opinionMode, matching]);

  // matching이 null이면 자격요건만 표시 (회사 문서 미등록)
  if (!matching) {
    const constraints = analysis.analysis?.constraints || analysis.constraints || [];
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-bold text-blue-700">
            자격요건 추출 완료
          </span>
        </div>
        {analysis.analysis?.title && (
          <p className="text-sm font-medium text-slate-800">{analysis.analysis.title}</p>
        )}
        {constraints.length > 0 ? (
          <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
            {constraints.map((c: { category?: string; text?: string; description?: string }, idx: number) => (
              <div key={idx} className="flex items-start gap-2 text-xs">
                <AlertCircle size={14} className="mt-0.5 shrink-0 text-blue-500" />
                <div>
                  {c.category && <span className="font-medium text-slate-500">[{c.category}] </span>}
                  <span className="text-slate-700">{c.text || c.description}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">추출된 자격요건이 없습니다.</p>
        )}
        <div className="rounded-lg bg-blue-50 border border-blue-200 px-3 py-2">
          <p className="text-xs text-blue-700">
            회사 문서를 등록하면 GO/NO-GO 판정과 맞춤 매칭 분석을 받을 수 있어요.
          </p>
        </div>
      </div>
    );
  }

  const score = Math.round(matching.overall_score || 0);
  const isGo = matching.recommendation?.toLowerCase().includes('go') &&
    !matching.recommendation?.toLowerCase().includes('no-go');

  return (
    <div className="space-y-3">
      {/* Header badge */}
      <div className="flex items-center gap-3">
        <span
          className={`rounded-full px-3 py-1 text-sm font-bold ${
            isGo ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
          }`}
        >
          {isGo ? 'GO' : 'NO-GO'}
        </span>
        <span className="text-lg font-bold text-slate-800">{score}%</span>
        <span className="text-sm text-slate-500">적합도</span>
      </div>

      {/* Summary */}
      {matching.summary && (
        <p className="text-sm text-slate-600 leading-relaxed">{matching.summary}</p>
      )}

      {/* Counts */}
      <div className="flex gap-4 text-xs">
        <span className="flex items-center gap-1 text-emerald-600">
          <CheckCircle2 size={14} /> 충족 {matching.met_count}
        </span>
        <span className="flex items-center gap-1 text-amber-600">
          <AlertCircle size={14} /> 부분 {matching.partially_met_count}
        </span>
        <span className="flex items-center gap-1 text-red-500">
          <XCircle size={14} /> 미충족 {matching.not_met_count}
        </span>
      </div>

      {/* Requirements list */}
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
                {m.evidence && (
                  <p className="mt-0.5 text-slate-500">{m.evidence}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Opinion mode toggle */}
      <div>
        <p className="text-xs font-semibold text-slate-600 mb-1">의견 모드</p>
        <div className="flex gap-2">
          {(Object.keys(matching.assistant_opinions || {}) as OpinionMode[])
            .filter((mode, index, arr) => arr.indexOf(mode) === index)
            .map((mode) => (
              <button
                key={mode}
                type="button"
                className={`rounded-full border px-3 py-0.5 text-xs font-medium ${
                  opinionMode === mode
                    ? 'border-kira-700 bg-kira-700 text-white'
                    : 'border-slate-300 bg-white text-slate-600 hover:border-kira-300'
                }`}
                onClick={() => setOpinionMode(mode)}
              >
                {modeLabel[mode] || mode}
              </button>
            ))}
        </div>
      </div>

      {/* Opinion actions */}
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

      {/* Proposal generation button — only when matching (company docs) is available */}
      {matching && (
        <button
          type="button"
          onClick={() =>
            onAction?.({
              type: 'generate_proposal',
              bidNoticeId: analysis.filename || 'unknown',
              bidTitle: analysis.analysis?.title || '',
            })
          }
          className="mt-1 flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-kira-600 to-kira-700 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:from-kira-700 hover:to-kira-800 transition-all"
        >
          <Sparkles size={14} />
          제안서 초안 생성
        </button>
      )}
    </div>
  );
};

export default AnalysisResultView;
