import React, { useState, useEffect } from 'react';
import { Package, FileText, Upload, DollarSign, ClipboardCheck, Loader2, RefreshCw } from 'lucide-react';
import type { PackageItem } from '../../../services/studioApi';
import { listPackageItems } from '../../../services/studioApi';

interface PackageStageProps {
  projectId: string;
  procurementDomain?: string;
  contractMethod?: string;
}

type CategoryKey = 'generated_document' | 'evidence' | 'administrative' | 'price';

const CATEGORY_META: Record<CategoryKey, { label: string; icon: React.ElementType; color: string }> = {
  generated_document: { label: '자동 생성 문서', icon: FileText, color: 'text-blue-600 bg-blue-50 border-blue-200' },
  evidence: { label: '증빙 서류', icon: Upload, color: 'text-amber-600 bg-amber-50 border-amber-200' },
  administrative: { label: '행정 서류', icon: ClipboardCheck, color: 'text-slate-600 bg-slate-50 border-slate-200' },
  price: { label: '가격 서류', icon: DollarSign, color: 'text-green-600 bg-green-50 border-green-200' },
};

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  missing: { label: '미제출', className: 'bg-red-50 text-red-700' },
  ready_to_generate: { label: '생성 가능', className: 'bg-blue-50 text-blue-700' },
  generated: { label: '생성 완료', className: 'bg-green-50 text-green-700' },
  uploaded: { label: '업로드됨', className: 'bg-green-50 text-green-700' },
  verified: { label: '확인됨', className: 'bg-green-100 text-green-800' },
  waived: { label: '면제', className: 'bg-slate-100 text-slate-500' },
};

export default function PackageStage({ projectId, procurementDomain, contractMethod }: PackageStageProps) {
  const [items, setItems] = useState<PackageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadItems = () => {
    setLoading(true);
    setError('');
    listPackageItems(projectId)
      .then(setItems)
      .catch((err) => setError(err.message || '패키지 항목을 불러올 수 없습니다'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadItems();
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
        {error}
        <button onClick={loadItems} className="ml-2 underline">다시 시도</button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-16">
        <Package size={40} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-500">아직 분류된 패키지 항목이 없습니다.</p>
        <p className="text-xs text-slate-400 mt-1">공고 단계에서 패키지 분류를 실행해주세요.</p>
      </div>
    );
  }

  // Group items by category
  const groups = groupByCategory(items);
  const totalItems = items.length;
  const completedItems = items.filter(
    (i) => i.status === 'generated' || i.status === 'uploaded' || i.status === 'verified',
  ).length;

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">제출 패키지</h2>
          {procurementDomain && contractMethod && (
            <p className="text-sm text-slate-500 mt-0.5">
              {domainLabel(procurementDomain)} / {methodLabel(contractMethod)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">
            {completedItems}/{totalItems} 완료
          </span>
          <button onClick={loadItems} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-slate-100 mb-6 overflow-hidden">
        <div
          className="h-full rounded-full bg-kira-500 transition-all"
          style={{ width: `${totalItems > 0 ? (completedItems / totalItems) * 100 : 0}%` }}
        />
      </div>

      {/* Category groups */}
      <div className="space-y-6">
        {(['generated_document', 'evidence', 'administrative', 'price'] as CategoryKey[]).map((cat) => {
          const catItems = groups[cat];
          if (!catItems || catItems.length === 0) return null;
          const meta = CATEGORY_META[cat];
          const Icon = meta.icon;

          return (
            <div key={cat} className={`rounded-xl border p-4 ${meta.color}`}>
              <div className="flex items-center gap-2 mb-3">
                <Icon size={18} />
                <h3 className="text-sm font-semibold">{meta.label}</h3>
                <span className="text-xs opacity-70">{catItems.length}건</span>
              </div>
              <div className="space-y-2">
                {catItems.map((item) => {
                  const statusInfo = STATUS_LABELS[item.status] || { label: item.status, className: 'bg-slate-100 text-slate-600' };
                  return (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-lg bg-white/80 px-3 py-2.5"
                    >
                      <span className="text-sm text-slate-800">{item.document_label}</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusInfo.className}`}>
                        {statusInfo.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


function groupByCategory(items: PackageItem[]): Record<string, PackageItem[]> {
  const groups: Record<string, PackageItem[]> = {};
  for (const item of items) {
    if (!groups[item.package_category]) {
      groups[item.package_category] = [];
    }
    groups[item.package_category].push(item);
  }
  return groups;
}

function domainLabel(domain: string): string {
  const labels: Record<string, string> = {
    service: '용역',
    goods: '물품',
    construction: '공사',
  };
  return labels[domain] || domain;
}

function methodLabel(method: string): string {
  const labels: Record<string, string> = {
    negotiated: '협상에 의한 계약',
    pq: '적격심사',
    adequacy: '적정가격',
    lowest_price: '최저가',
  };
  return labels[method] || method;
}
