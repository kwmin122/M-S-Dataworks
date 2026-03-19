import React from 'react';
import { FileText, Building2, Palette, ClipboardList } from 'lucide-react';
import type { StudioProject } from '../../../services/studioApi';

interface GenerateContractViewProps {
  project: StudioProject;
}

export default function GenerateContractView({ project }: GenerateContractViewProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">생성 입력 계약</h3>
      <p className="text-xs text-slate-400 mb-4">
        이 정보가 제안서 생성에 사용됩니다. 변경하려면 해당 단계로 돌아가세요.
      </p>

      <div className="space-y-3">
        {/* Analysis Snapshot */}
        <ContractItem
          icon={FileText}
          label="공고 분석 스냅샷"
          value={project.active_analysis_snapshot_id
            ? `ID: ${project.active_analysis_snapshot_id.slice(0, 12)}...`
            : '없음'}
          status={project.active_analysis_snapshot_id ? 'ready' : 'missing'}
        />

        {/* Company Context */}
        <ContractItem
          icon={Building2}
          label="회사 역량"
          value="공유 + 스테이징 자산 병합 사용"
          status="ready"
        />

        {/* Pinned Style */}
        <ContractItem
          icon={Palette}
          label="핀 설정 스타일"
          value={project.pinned_style_skill_id
            ? `ID: ${project.pinned_style_skill_id.slice(0, 12)}...`
            : '기본 문체 사용'}
          status={project.pinned_style_skill_id ? 'ready' : 'default'}
        />

        {/* Document Type */}
        <ContractItem
          icon={ClipboardList}
          label="생성 대상"
          value="기술 제안서 (proposal)"
          status="ready"
        />
      </div>
    </div>
  );
}


function ContractItem({
  icon: Icon,
  label,
  value,
  status,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  status: 'ready' | 'missing' | 'default';
}) {
  const statusColors = {
    ready: 'text-green-600 bg-green-50',
    missing: 'text-red-600 bg-red-50',
    default: 'text-slate-500 bg-slate-50',
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-100 px-3 py-2.5">
      <div className={`p-1.5 rounded-lg ${statusColors[status]}`}>
        <Icon size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <span className="text-sm text-slate-700 font-medium">{label}</span>
        <span className="text-xs text-slate-400 ml-2">{value}</span>
      </div>
    </div>
  );
}
