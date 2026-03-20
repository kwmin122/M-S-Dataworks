import React from 'react';
import { FileText, Building2, Palette, ClipboardList, Hash } from 'lucide-react';
import type { StudioProject, GenerationContract } from '../../../services/studioApi';

interface GenerateContractViewProps {
  project: StudioProject;
  /** Actual contract returned after generation — shows real computed values */
  contract?: GenerationContract | null;
}

export default function GenerateContractView({ project, contract }: GenerateContractViewProps) {
  // Post-generation: show actual computed contract
  if (contract) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">생성 입력 계약 (실제 사용됨)</h3>
        <p className="text-xs text-slate-400 mb-4">
          이 정보가 제안서 생성에 실제로 사용되었습니다.
        </p>
        <div className="space-y-2">
          <ContractRow label="분석 스냅샷 ID" value={contract.snapshot_id} />
          <ContractRow label="스냅샷 버전" value={`v${contract.snapshot_version}`} />
          <ContractRow label="회사 자산 수" value={`${contract.company_assets_count}건`} />
          <ContractRow label="회사 컨텍스트 길이" value={`${contract.company_context_length}자`} />
          <ContractRow
            label="핀 스타일"
            value={contract.pinned_style_name
              ? `${contract.pinned_style_name} (v${contract.pinned_style_version})`
              : '없음 — 기본 문체'}
          />
          <ContractRow label="문서 유형" value={contract.doc_type} />
          <ContractRow label="목표 페이지" value={`${contract.total_pages}p`} />
        </div>
      </div>
    );
  }

  // Pre-generation: show expected inputs from project state
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">생성 입력 계약 (예상)</h3>
      <p className="text-xs text-slate-400 mb-4">
        이 정보가 제안서 생성에 사용됩니다. 변경하려면 해당 단계로 돌아가세요.
      </p>

      <div className="space-y-3">
        <ContractItem
          icon={FileText}
          label="공고 분석 스냅샷"
          value={project.active_analysis_snapshot_id
            ? `ID: ${project.active_analysis_snapshot_id.slice(0, 12)}...`
            : '없음'}
          status={project.active_analysis_snapshot_id ? 'ready' : 'missing'}
        />

        <ContractItem
          icon={Building2}
          label="회사 역량"
          value="공유 + 스테이징 자산 병합 사용"
          status="ready"
        />

        <ContractItem
          icon={Palette}
          label="핀 설정 스타일"
          value={project.pinned_style_skill_id
            ? `ID: ${project.pinned_style_skill_id.slice(0, 12)}...`
            : '기본 문체 사용'}
          status={project.pinned_style_skill_id ? 'ready' : 'default'}
        />

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


function ContractRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2">
      <span className="text-sm text-slate-600">{label}</span>
      <span className="text-sm font-medium text-slate-800">{value}</span>
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
