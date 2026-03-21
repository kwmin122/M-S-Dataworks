import React, { useState, useEffect, useCallback } from 'react';
import {
  Package,
  FileText,
  Upload,
  DollarSign,
  ClipboardCheck,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Trash2,
  Plus,
  Settings2,
  Info,
} from 'lucide-react';
import type { PackageItem } from '../../../services/studioApi';
import {
  listPackageItems,
  overridePackageClassification,
  updatePackageItemStatus,
} from '../../../services/studioApi';

interface PackageStageProps {
  projectId: string;
  procurementDomain?: string;
  contractMethod?: string;
  confidence?: number;
  reviewRequired?: boolean;
  matchedSignals?: string[];
  classifierWarnings?: string[];
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

const DOMAIN_OPTIONS = [
  { value: 'service', label: '용역' },
  { value: 'goods', label: '물품' },
  { value: 'construction', label: '공사' },
];

const METHOD_OPTIONS = [
  { value: 'negotiated', label: '협상에 의한 계약' },
  { value: 'pq', label: '적격심사' },
  { value: 'adequacy', label: '적정가격' },
  { value: 'lowest_price', label: '최저가' },
];

const CATEGORY_OPTIONS: { value: CategoryKey; label: string }[] = [
  { value: 'evidence', label: '증빙 서류' },
  { value: 'administrative', label: '행정 서류' },
  { value: 'price', label: '가격 서류' },
  { value: 'generated_document', label: '자동 생성 문서' },
];

export default function PackageStage({
  projectId,
  procurementDomain,
  contractMethod,
  confidence,
  reviewRequired,
  matchedSignals,
  classifierWarnings,
}: PackageStageProps) {
  const [items, setItems] = useState<PackageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Override panel state
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideDomain, setOverrideDomain] = useState(procurementDomain ?? '');
  const [overrideMethod, setOverrideMethod] = useState(contractMethod ?? '');
  const [overridePpt, setOverridePpt] = useState<boolean | null>(null);
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);
  const [overrideError, setOverrideError] = useState('');

  // Add item form state
  const [addingToCategory, setAddingToCategory] = useState<CategoryKey | null>(null);
  const [newItemLabel, setNewItemLabel] = useState('');
  const [addItemSubmitting, setAddItemSubmitting] = useState(false);

  // Item action state
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  // Active domain/method (may be overridden)
  const [activeDomain, setActiveDomain] = useState(procurementDomain);
  const [activeMethod, setActiveMethod] = useState(contractMethod);

  // Sync when props change (e.g. re-classify)
  useEffect(() => {
    setActiveDomain(procurementDomain);
    setActiveMethod(contractMethod);
    setOverrideDomain(procurementDomain ?? '');
    setOverrideMethod(contractMethod ?? '');
  }, [procurementDomain, contractMethod]);

  const loadItems = useCallback(() => {
    setLoading(true);
    setError('');
    listPackageItems(projectId)
      .then(setItems)
      .catch((err) => setError(err.message || '패키지 항목을 불러올 수 없습니다'))
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  // --- Override submission ---
  const handleOverrideSubmit = async () => {
    setOverrideSubmitting(true);
    setOverrideError('');
    try {
      const params: Parameters<typeof overridePackageClassification>[1] = {};
      if (overrideDomain && overrideDomain !== activeDomain) {
        params.procurement_domain = overrideDomain;
      }
      if (overrideMethod && overrideMethod !== activeMethod) {
        params.contract_method = overrideMethod;
      }
      if (overridePpt !== null) {
        // Check current PPT state
        const hasPpt = items.some((i) => i.generation_target === 'presentation');
        if (overridePpt !== hasPpt) {
          params.include_presentation = overridePpt;
        }
      }

      // If no actual changes, skip
      if (Object.keys(params).length === 0) {
        setOverrideOpen(false);
        return;
      }

      const result = await overridePackageClassification(projectId, params);
      setItems(result.package_items);
      if (params.procurement_domain) setActiveDomain(params.procurement_domain);
      if (params.contract_method) setActiveMethod(params.contract_method);
      setOverrideOpen(false);
      setOverridePpt(null);
    } catch (err: unknown) {
      setOverrideError(err instanceof Error ? err.message : '수정 적용 실패');
    } finally {
      setOverrideSubmitting(false);
    }
  };

  // --- Waive item ---
  const handleWaive = async (itemId: string) => {
    setActionLoading((prev) => ({ ...prev, [itemId]: true }));
    try {
      await updatePackageItemStatus(projectId, itemId, 'waived');
      setItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'waived' } : i)));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '면제 처리 실패');
    } finally {
      setActionLoading((prev) => ({ ...prev, [itemId]: false }));
    }
  };

  // --- Remove item ---
  const handleRemoveItem = async (itemId: string) => {
    setActionLoading((prev) => ({ ...prev, [itemId]: true }));
    try {
      const result = await overridePackageClassification(projectId, {
        remove_item_ids: [itemId],
      });
      setItems(result.package_items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '항목 삭제 실패');
    } finally {
      setActionLoading((prev) => ({ ...prev, [itemId]: false }));
    }
  };

  // --- Add item ---
  const handleAddItem = async (category: CategoryKey) => {
    if (!newItemLabel.trim()) return;
    setAddItemSubmitting(true);
    try {
      const result = await overridePackageClassification(projectId, {
        add_items: [
          {
            document_label: newItemLabel.trim(),
            package_category: category,
            required: true,
          },
        ],
      });
      setItems(result.package_items);
      setNewItemLabel('');
      setAddingToCategory(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '항목 추가 실패');
    } finally {
      setAddItemSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  if (error && items.length === 0) {
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

  const hasPpt = items.some((i) => i.generation_target === 'presentation');

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">제출 패키지</h2>
          {activeDomain && activeMethod && (
            <p className="text-sm text-slate-500 mt-0.5">
              {domainLabel(activeDomain)} / {methodLabel(activeMethod)}
              {confidence != null && (
                <span className="ml-2 text-xs text-slate-400">
                  (확신도 {Math.round(confidence * 100)}%)
                </span>
              )}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">
            {completedItems}/{totalItems} 완료
          </span>
          <button onClick={loadItems} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400" title="새로고침">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Inline error for action failures */}
      {error && items.length > 0 && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 mb-4 text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-400 hover:text-red-600 text-xs ml-2">닫기</button>
        </div>
      )}

      {/* Review required warning + override trigger */}
      {reviewRequired && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 mb-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-amber-800">
                자동 분류 확신 낮음 — 검토가 필요합니다
              </p>
              {classifierWarnings && classifierWarnings.length > 0 && (
                <ul className="mt-1 text-xs text-amber-600 list-disc list-inside">
                  {classifierWarnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              )}
            </div>
            <button
              onClick={() => setOverrideOpen(!overrideOpen)}
              className="flex items-center gap-1 text-xs font-medium text-amber-700 hover:text-amber-900 bg-amber-100 hover:bg-amber-200 px-2.5 py-1 rounded-lg transition-colors shrink-0 ml-3"
            >
              <Settings2 size={14} />
              분류 수정
              {overrideOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
        </div>
      )}

      {/* Override toggle for non-reviewRequired (always accessible) */}
      {!reviewRequired && (
        <div className="mb-4 flex justify-end">
          <button
            onClick={() => setOverrideOpen(!overrideOpen)}
            className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-lg transition-colors"
          >
            <Settings2 size={14} />
            분류 수정
            {overrideOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      )}

      {/* Override panel */}
      {overrideOpen && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4 space-y-4">
          <h3 className="text-sm font-semibold text-slate-700">분류 결과 수정</h3>

          {/* Matched signals explanation */}
          {matchedSignals && matchedSignals.length > 0 && (
            <div className="rounded-lg bg-slate-50 border border-slate-100 p-3">
              <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 mb-1.5">
                <Info size={13} />
                분류 근거 (자동 탐지 시그널)
              </div>
              <ul className="text-xs text-slate-600 space-y-0.5">
                {matchedSignals.map((s, i) => (
                  <li key={i} className="flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-full bg-slate-400 shrink-0" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            {/* Domain override */}
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">조달 유형</label>
              <select
                value={overrideDomain}
                onChange={(e) => setOverrideDomain(e.target.value)}
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kira-500/30"
              >
                <option value="">선택</option>
                {DOMAIN_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* Method override */}
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">계약 방식</label>
              <select
                value={overrideMethod}
                onChange={(e) => setOverrideMethod(e.target.value)}
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kira-500/30"
              >
                <option value="">선택</option>
                {METHOD_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Presentation toggle */}
          <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={overridePpt !== null ? overridePpt : hasPpt}
              onChange={(e) => setOverridePpt(e.target.checked)}
              className="rounded border-slate-300 text-kira-500 focus:ring-kira-500/30"
            />
            발표자료 (PPT) 포함
          </label>

          {overrideError && (
            <p className="text-xs text-red-600">{overrideError}</p>
          )}

          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={handleOverrideSubmit}
              disabled={overrideSubmitting}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-white bg-kira-500 hover:bg-kira-600 disabled:opacity-50 px-4 py-2 rounded-lg transition-colors"
            >
              {overrideSubmitting && <Loader2 size={14} className="animate-spin" />}
              분류 수정 적용
            </button>
            <button
              onClick={() => {
                setOverrideOpen(false);
                setOverrideError('');
                setOverrideDomain(activeDomain ?? '');
                setOverrideMethod(activeMethod ?? '');
                setOverridePpt(null);
              }}
              className="text-sm text-slate-500 hover:text-slate-700 px-3 py-2"
            >
              취소
            </button>
          </div>
        </div>
      )}

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
          if (!catItems || catItems.length === 0) {
            // Still allow adding items to empty categories
            return (
              <div key={cat}>
                {renderAddItemButton(cat)}
              </div>
            );
          }
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
                  const isActionLoading = actionLoading[item.id] ?? false;
                  const canWaive = item.status === 'missing';
                  const canRemove = item.status === 'missing' || item.status === 'waived';

                  return (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-lg bg-white/80 px-3 py-2.5 group"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm text-slate-800 truncate">{item.document_label}</span>
                        {!item.required && (
                          <span className="text-[10px] text-slate-400 shrink-0">선택</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {/* Action buttons — visible on hover or when loading */}
                        {isActionLoading ? (
                          <Loader2 size={14} className="animate-spin text-slate-400" />
                        ) : (
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {canWaive && (
                              <button
                                onClick={() => handleWaive(item.id)}
                                className="text-xs text-slate-400 hover:text-slate-600 px-1.5 py-0.5 rounded hover:bg-slate-100"
                                title="면제 처리"
                              >
                                면제
                              </button>
                            )}
                            {canRemove && (
                              <button
                                onClick={() => handleRemoveItem(item.id)}
                                className="text-slate-300 hover:text-red-500 p-0.5 rounded hover:bg-red-50"
                                title="항목 삭제"
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
                          </div>
                        )}
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusInfo.className}`}>
                          {statusInfo.label}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Add item for this category */}
              {renderAddItemInline(cat)}
            </div>
          );
        })}
      </div>
    </div>
  );

  // --- Inline add item form (inside a category card) ---
  function renderAddItemInline(cat: CategoryKey) {
    if (addingToCategory === cat) {
      return (
        <div className="mt-2 flex items-center gap-2">
          <input
            type="text"
            value={newItemLabel}
            onChange={(e) => setNewItemLabel(e.target.value)}
            placeholder="항목명 입력"
            className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-kira-500/30"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && newItemLabel.trim()) handleAddItem(cat);
              if (e.key === 'Escape') { setAddingToCategory(null); setNewItemLabel(''); }
            }}
          />
          <button
            onClick={() => handleAddItem(cat)}
            disabled={addItemSubmitting || !newItemLabel.trim()}
            className="inline-flex items-center gap-1 text-xs font-medium text-white bg-kira-500 hover:bg-kira-600 disabled:opacity-50 px-3 py-1.5 rounded-lg"
          >
            {addItemSubmitting ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            추가
          </button>
          <button
            onClick={() => { setAddingToCategory(null); setNewItemLabel(''); }}
            className="text-xs text-slate-400 hover:text-slate-600 px-2 py-1.5"
          >
            취소
          </button>
        </div>
      );
    }
    return (
      <button
        onClick={() => { setAddingToCategory(cat); setNewItemLabel(''); }}
        className="mt-2 flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
      >
        <Plus size={13} />
        항목 추가
      </button>
    );
  }

  // --- Standalone add item button (for empty categories) ---
  function renderAddItemButton(cat: CategoryKey) {
    const meta = CATEGORY_META[cat];
    if (addingToCategory === cat) {
      return (
        <div className={`rounded-xl border p-4 ${meta.color}`}>
          <div className="flex items-center gap-2 mb-3">
            <meta.icon size={18} />
            <h3 className="text-sm font-semibold">{meta.label}</h3>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newItemLabel}
              onChange={(e) => setNewItemLabel(e.target.value)}
              placeholder="항목명 입력"
              className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-kira-500/30"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newItemLabel.trim()) handleAddItem(cat);
                if (e.key === 'Escape') { setAddingToCategory(null); setNewItemLabel(''); }
              }}
            />
            <button
              onClick={() => handleAddItem(cat)}
              disabled={addItemSubmitting || !newItemLabel.trim()}
              className="inline-flex items-center gap-1 text-xs font-medium text-white bg-kira-500 hover:bg-kira-600 disabled:opacity-50 px-3 py-1.5 rounded-lg"
            >
              {addItemSubmitting ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
              추가
            </button>
            <button
              onClick={() => { setAddingToCategory(null); setNewItemLabel(''); }}
              className="text-xs text-slate-400 hover:text-slate-600 px-2 py-1.5"
            >
              취소
            </button>
          </div>
        </div>
      );
    }
    // Don't render empty categories unless user explicitly wants to add
    return null;
  }
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
