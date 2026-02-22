import React, { useState } from 'react';
import { Download } from 'lucide-react';
import Button from '../Button';

interface EvalJob {
  id: string;
  bidNoticeId: string;
  isEligible: boolean | null;
  evaluationReason: string;
  actionPlan: string | null;
  bidNotice: {
    title: string;
    region: string | null;
    deadlineAt: string | null;
    url: string | null;
  };
}

interface MultiAnalysisPanelProps {
  organizationId: string;
}

const MultiAnalysisPanel: React.FC<MultiAnalysisPanelProps> = ({ organizationId }) => {
  const [jobs, setJobs] = useState<EvalJob[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadJobs = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/internal/evaluation-jobs?organizationId=${organizationId}`);
      const data = await res.json() as { jobs: EvalJob[] };
      setJobs(data.jobs);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExcel = () => {
    window.open(`/api/export/evaluations?organizationId=${organizationId}`, '_blank');
  };

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="flex items-center justify-between p-3 border-b border-slate-200 bg-slate-50">
        <Button size="sm" onClick={() => void loadJobs()} disabled={isLoading}>
          {isLoading ? '불러오는 중...' : '평가 결과 조회'}
        </Button>
        <button
          type="button"
          onClick={handleExcel}
          disabled={!jobs.length}
          className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          <Download className="h-3 w-3" /> 엑셀 다운로드
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {jobs.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            평가 결과가 없습니다. 공고 검색 후 평가를 실행하세요.
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">공고명</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">지역</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">마감</th>
                <th className="px-3 py-2 text-center font-semibold text-slate-600">판정</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {jobs.map((j) => (
                <tr key={j.id} className="hover:bg-slate-50">
                  <td className="px-3 py-2 text-slate-700 max-w-[160px] truncate">{j.bidNotice.title}</td>
                  <td className="px-3 py-2 text-slate-500">{j.bidNotice.region || '-'}</td>
                  <td className="px-3 py-2 text-slate-500">
                    {j.bidNotice.deadlineAt ? j.bidNotice.deadlineAt.slice(0, 10) : '-'}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {j.isEligible === true && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700 font-semibold">GO</span>}
                    {j.isEligible === false && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">NO-GO</span>}
                    {j.isEligible === null && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-700">대기</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default MultiAnalysisPanel;
