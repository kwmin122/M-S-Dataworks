import React, { useState, useEffect, useCallback } from 'react';
import {
  Building2, Users, Briefcase, Shield, FileText, Plus, ArrowUpCircle,
  Loader2, AlertCircle, CheckCircle2, ChevronDown, ChevronUp,
} from 'lucide-react';
import type { AssetCategory, MergedCompanyData, CompanyAsset } from '../../../services/studioApi';
import {
  getCompanyMerged, addCompanyAsset, listCompanyAssets, promoteCompanyAsset,
} from '../../../services/studioApi';

interface CompanyStageProps {
  projectId: string;
}

// --- Asset form configs ---

type FormField = { key: string; label: string; type: 'text' | 'number' | 'textarea' };

const ASSET_FORMS: Record<string, { label: string; icon: React.ElementType; fields: FormField[] }> = {
  track_record: {
    label: '실적',
    icon: Briefcase,
    fields: [
      { key: 'project_name', label: '프로젝트명', type: 'text' },
      { key: 'client_name', label: '발주처', type: 'text' },
      { key: 'contract_amount', label: '계약금액(원)', type: 'number' },
      { key: 'description', label: '설명', type: 'textarea' },
    ],
  },
  personnel: {
    label: '인력',
    icon: Users,
    fields: [
      { key: 'name', label: '이름', type: 'text' },
      { key: 'role', label: '역할', type: 'text' },
      { key: 'years_experience', label: '경력(년)', type: 'number' },
      { key: 'description', label: '설명', type: 'textarea' },
    ],
  },
  profile: {
    label: '회사 기본정보',
    icon: Building2,
    fields: [
      { key: 'company_name', label: '회사명', type: 'text' },
      { key: 'business_type', label: '업종', type: 'text' },
      { key: 'business_number', label: '사업자등록번호', type: 'text' },
      { key: 'headcount', label: '직원 수', type: 'number' },
    ],
  },
  technology: {
    label: '기술',
    icon: Shield,
    fields: [
      { key: 'name', label: '기술명', type: 'text' },
      { key: 'level', label: '수준', type: 'text' },
      { key: 'description', label: '설명', type: 'textarea' },
    ],
  },
  certification: {
    label: '인증',
    icon: CheckCircle2,
    fields: [
      { key: 'name', label: '인증명', type: 'text' },
      { key: 'issuer', label: '발급기관', type: 'text' },
      { key: 'description', label: '설명', type: 'textarea' },
    ],
  },
  raw_document: {
    label: '기타 문서',
    icon: FileText,
    fields: [
      { key: 'name', label: '문서명', type: 'text' },
      { key: 'description', label: '설명', type: 'textarea' },
    ],
  },
};

const PROMOTABLE: Set<string> = new Set(['track_record', 'personnel', 'profile']);

export default function CompanyStage({ projectId }: CompanyStageProps) {
  const [merged, setMerged] = useState<MergedCompanyData | null>(null);
  const [stagingAssets, setStagingAssets] = useState<CompanyAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addingCategory, setAddingCategory] = useState<string | null>(null);
  const [promoting, setPromoting] = useState<string | null>(null);
  const [expandedSection, setExpandedSection] = useState<string | null>('profile');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [mergedData, assets] = await Promise.all([
        getCompanyMerged(projectId),
        listCompanyAssets(projectId),
      ]);
      setMerged(mergedData);
      setStagingAssets(assets);
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터를 불러올 수 없습니다');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadData(); }, [loadData]);

  const handlePromote = useCallback(async (assetId: string) => {
    if (!confirm('이 자산을 공유 DB에 승격하시겠습니까? 승격하면 다른 프로젝트에서도 사용 가능합니다.')) return;
    setPromoting(assetId);
    try {
      await promoteCompanyAsset(projectId, assetId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '승격 실패');
    } finally {
      setPromoting(null);
    }
  }, [projectId, loadData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  if (error && !merged) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700 flex items-center gap-2">
        <AlertCircle size={16} />
        {error}
        <button onClick={loadData} className="ml-2 underline">다시 시도</button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">회사 역량</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            프로젝트에 필요한 회사 자산을 관리하세요
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 mb-4">
          {error}
        </div>
      )}

      {/* Asset sections — profile included in the unified list */}
      {(['profile', 'track_record', 'personnel', 'technology', 'certification', 'raw_document'] as string[]).map((category) => {
        const formConfig = ASSET_FORMS[category];
        const Icon = formConfig.icon;
        const isExpanded = expandedSection === category;

        // Gather items for this category from merged view
        let items: Array<Record<string, unknown> & { source: string }>;
        if (category === 'profile') {
          // Profile: show as a single-item list if present
          items = merged?.profile ? [merged.profile as Record<string, unknown> & { source: string }] : [];
        } else if (category === 'track_record') {
          items = merged?.track_records ?? [];
        } else if (category === 'personnel') {
          items = merged?.personnel ?? [];
        } else {
          items = merged?.other_assets?.filter(a => a.asset_category === category) ?? [];
        }

        const stagingCount = items.filter(i => i.source === 'staging').length;

        return (
          <div key={category} className="rounded-xl border border-slate-200 mb-3 bg-white overflow-hidden">
            <button
              onClick={() => setExpandedSection(isExpanded ? null : category)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Icon size={18} className="text-slate-500" />
                <h3 className="text-sm font-semibold text-slate-700">{formConfig.label}</h3>
                <span className="text-xs text-slate-400">{items.length}건</span>
                {stagingCount > 0 && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-700">
                    +{stagingCount} 스테이징
                  </span>
                )}
              </div>
              {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
            </button>

            {isExpanded && (
              <div className="px-4 pb-4 border-t border-slate-100">
                {/* Existing items */}
                {items.length > 0 && (
                  <div className="space-y-2 mt-3">
                    {items.map((item, idx) => (
                      <AssetRow
                        key={String(item.id ?? idx)}
                        item={item}
                        category={category}
                        onPromote={handlePromote}
                        isPromoting={promoting === item.id}
                        stagingAssets={stagingAssets}
                      />
                    ))}
                  </div>
                )}

                {items.length === 0 && addingCategory !== category && (
                  <p className="text-sm text-slate-400 mt-3">등록된 {formConfig.label}이(가) 없습니다.</p>
                )}

                {/* Add form */}
                {addingCategory === category ? (
                  <AddAssetForm
                    projectId={projectId}
                    category={category as AssetCategory}
                    fields={formConfig.fields}
                    onSaved={() => { setAddingCategory(null); loadData(); }}
                    onCancel={() => setAddingCategory(null)}
                  />
                ) : (
                  <button
                    onClick={() => setAddingCategory(category)}
                    className="mt-3 flex items-center gap-1 text-sm text-kira-600 hover:text-kira-700"
                  >
                    <Plus size={14} />
                    {formConfig.label} 추가
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- Sub-components ---

function AssetRow({
  item,
  category,
  onPromote,
  isPromoting,
  stagingAssets,
}: {
  item: Record<string, unknown>;
  category: string;
  onPromote: (id: string) => void;
  isPromoting: boolean;
  stagingAssets: CompanyAsset[];
}) {
  const isStaging = item.source === 'staging';
  const canPromote = isStaging && PROMOTABLE.has(category);
  const alreadyPromoted = isStaging && stagingAssets.find(
    a => a.id === item.id && a.promoted_at !== null
  );

  // Pick display fields based on category
  const primaryLabel = String(
    item.project_name || item.name || item.company_name || item.label || '(무제)'
  );
  const secondaryLabel = String(
    item.client_name || item.role || item.business_type || item.issuer || ''
  );

  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2.5 bg-slate-50/50">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-800 truncate">{primaryLabel}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded-full ${
            isStaging
              ? alreadyPromoted
                ? 'bg-green-50 text-green-700'
                : 'bg-amber-50 text-amber-700'
              : 'bg-slate-100 text-slate-500'
          }`}>
            {isStaging ? (alreadyPromoted ? '승격됨' : '스테이징') : '공유'}
          </span>
        </div>
        {secondaryLabel && (
          <span className="text-xs text-slate-400">{secondaryLabel}</span>
        )}
      </div>
      {canPromote && !alreadyPromoted && (
        <button
          onClick={() => onPromote(String(item.id))}
          disabled={isPromoting}
          className="flex items-center gap-1 text-xs text-kira-600 hover:text-kira-700 disabled:opacity-50 ml-2"
        >
          {isPromoting ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <ArrowUpCircle size={14} />
          )}
          승격
        </button>
      )}
    </div>
  );
}


function AddAssetForm({
  projectId,
  category,
  fields,
  onSaved,
  onCancel,
}: {
  projectId: string;
  category: AssetCategory;
  fields: FormField[];
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Build content_json (convert number fields)
    const content: Record<string, unknown> = {};
    for (const field of fields) {
      const val = values[field.key]?.trim();
      if (!val) continue;
      content[field.key] = field.type === 'number' ? Number(val) : val;
    }

    // Require at least one field filled
    if (Object.keys(content).length === 0) {
      setError('최소 하나의 필드를 입력해주세요');
      return;
    }

    // Build label from first text field
    const label = String(Object.values(content)[0] ?? category);

    setSaving(true);
    setError('');
    try {
      await addCompanyAsset(projectId, {
        asset_category: category,
        label,
        content_json: content,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mt-3 p-3 rounded-lg border border-kira-200 bg-kira-50/30">
      <div className="space-y-2">
        {fields.map((field) => {
          const fieldId = `${category}-${field.key}`;
          return (
          <div key={field.key}>
            <label htmlFor={fieldId} className="block text-xs font-medium text-slate-600 mb-0.5">{field.label}</label>
            {field.type === 'textarea' ? (
              <textarea
                id={fieldId}
                className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-kira-400"
                rows={2}
                value={values[field.key] ?? ''}
                onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
              />
            ) : (
              <input
                id={fieldId}
                type={field.type}
                className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-kira-400"
                value={values[field.key] ?? ''}
                onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
              />
            )}
          </div>
          );
        })}
      </div>

      {error && (
        <p className="text-xs text-red-600 mt-2">{error}</p>
      )}

      <div className="flex items-center gap-2 mt-3">
        <button
          type="submit"
          disabled={saving}
          className="px-3 py-1.5 text-sm font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700 disabled:opacity-50"
        >
          {saving ? '저장 중...' : '저장'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700"
        >
          취소
        </button>
      </div>
    </form>
  );
}
