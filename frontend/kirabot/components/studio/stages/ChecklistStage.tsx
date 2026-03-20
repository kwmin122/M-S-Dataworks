import React, { useState, useEffect, useCallback } from 'react';
import {
  ClipboardCheck, CheckCircle2, Upload, XCircle, Loader2,
  AlertCircle, FileText, RefreshCw, ShieldCheck, Undo2,
} from 'lucide-react';
import type { PackageItem, PackageCompleteness } from '../../../services/studioApi';
import {
  listPackageItems, getPackageCompleteness, updatePackageItemStatus, attachEvidenceFile,
} from '../../../services/studioApi';

interface ChecklistStageProps {
  projectId: string;
}

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  missing: { label: '미제출', className: 'bg-red-50 text-red-700' },
  ready_to_generate: { label: '생성 가능', className: 'bg-blue-50 text-blue-700' },
  generated: { label: '생성 완료', className: 'bg-green-50 text-green-700' },
  uploaded: { label: '업로드됨', className: 'bg-green-50 text-green-700' },
  verified: { label: '확인됨', className: 'bg-green-100 text-green-800' },
  waived: { label: '면제', className: 'bg-slate-100 text-slate-500' },
};

export default function ChecklistStage({ projectId }: ChecklistStageProps) {
  const [items, setItems] = useState<PackageItem[]>([]);
  const [completeness, setCompleteness] = useState<PackageCompleteness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [itemsData, comp] = await Promise.all([
        listPackageItems(projectId),
        getPackageCompleteness(projectId),
      ]);
      setItems(itemsData);
      setCompleteness(comp);
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터를 불러올 수 없습니다');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleStatusChange = useCallback(async (itemId: string, status: 'verified' | 'waived' | 'missing') => {
    setActionLoading(itemId);
    try {
      await updatePackageItemStatus(projectId, itemId, status);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '상태 변경 실패');
    } finally {
      setActionLoading(null);
    }
  }, [projectId, loadData]);

  const handleEvidenceUpload = useCallback(async (itemId: string, file: File) => {
    setActionLoading(itemId);
    try {
      await attachEvidenceFile(projectId, itemId, file);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '파일 업로드 실패');
    } finally {
      setActionLoading(null);
    }
  }, [projectId, loadData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  if (error && items.length === 0) {
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
          <h2 className="text-lg font-bold text-slate-900">제출 체크리스트</h2>
          <p className="text-sm text-slate-500 mt-0.5">패키지 항목의 완성도를 관리하세요</p>
        </div>
        <button onClick={loadData} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
          <RefreshCw size={16} />
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 mb-4">{error}</div>
      )}

      {/* Completeness summary */}
      {completeness && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-slate-700">완성도</span>
            <span className="text-sm font-bold text-kira-600">{completeness.completeness_pct}%</span>
          </div>
          <div className="h-2 rounded-full bg-slate-100 mb-3 overflow-hidden">
            <div
              className="h-full rounded-full bg-kira-500 transition-all"
              style={{ width: `${completeness.completeness_pct}%` }}
            />
          </div>
          <div className="flex gap-4 text-xs text-slate-500">
            <span>전체 {completeness.total}건</span>
            <span>완료 {completeness.completed}건</span>
            {completeness.waived > 0 && <span>면제 {completeness.waived}건</span>}
            {completeness.required_remaining > 0 && (
              <span className="text-red-600">필수 미완료 {completeness.required_remaining}건</span>
            )}
          </div>
        </div>
      )}

      {/* Item list */}
      <div className="space-y-2">
        {items.map(item => (
          <ChecklistItem
            key={item.id}
            item={item}
            onStatusChange={handleStatusChange}
            onEvidenceUpload={handleEvidenceUpload}
            isLoading={actionLoading === item.id}
          />
        ))}
      </div>

      {items.length === 0 && (
        <div className="text-center py-16">
          <ClipboardCheck size={40} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm text-slate-500">패키지 항목이 없습니다.</p>
        </div>
      )}
    </div>
  );
}

function ChecklistItem({
  item,
  onStatusChange,
  onEvidenceUpload,
  isLoading,
}: {
  item: PackageItem;
  onStatusChange: (id: string, status: 'verified' | 'waived' | 'missing') => void;
  onEvidenceUpload: (id: string, file: File) => void;
  isLoading: boolean;
}) {
  const statusInfo = STATUS_LABELS[item.status] || { label: item.status, className: 'bg-slate-100' };
  const canVerify = item.status === 'generated' || item.status === 'uploaded';
  const canWaive = item.status === 'missing';
  const canRestore = item.status === 'waived';
  const canUploadEvidence = item.status === 'missing' && item.package_category !== 'generated_document';

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-800">{item.document_label}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusInfo.className}`}>
              {statusInfo.label}
            </span>
            {!item.required && (
              <span className="text-xs text-slate-400">(선택)</span>
            )}
          </div>
          {item.generation_target && (
            <span className="text-xs text-slate-400">자동 생성 대상: {item.generation_target}</span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1 ml-2 shrink-0">
          {isLoading && <Loader2 size={14} className="animate-spin text-slate-400" />}
          {!isLoading && canVerify && (
            <button
              onClick={() => onStatusChange(item.id, 'verified')}
              className="flex items-center gap-1 px-2 py-1 text-xs text-green-600 hover:bg-green-50 rounded-lg"
              title="확인 완료"
            >
              <ShieldCheck size={12} /> 확인
            </button>
          )}
          {!isLoading && canWaive && (
            <button
              onClick={() => onStatusChange(item.id, 'waived')}
              className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:bg-slate-50 rounded-lg"
              title="면제 처리"
            >
              <XCircle size={12} /> 면제
            </button>
          )}
          {!isLoading && canRestore && (
            <button
              onClick={() => onStatusChange(item.id, 'missing')}
              className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:bg-slate-50 rounded-lg"
              title="면제 취소"
            >
              <Undo2 size={12} /> 복구
            </button>
          )}
        </div>
      </div>

      {/* Evidence upload panel — only for non-generated_document + missing */}
      {canUploadEvidence && (
        <EvidenceUploadPanel
          onUpload={(file) => onEvidenceUpload(item.id, file)}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}

function EvidenceUploadPanel({
  onUpload,
  isLoading,
}: {
  onUpload: (file: File) => void;
  isLoading: boolean;
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  return (
    <div className="mt-3 pt-3 border-t border-slate-100">
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 cursor-pointer">
          <Upload size={12} />
          파일 선택
          <input
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setSelectedFile(f);
            }}
          />
        </label>
        {selectedFile && (
          <>
            <span className="text-xs text-slate-500 truncate max-w-48">{selectedFile.name}</span>
            <button
              onClick={() => { onUpload(selectedFile); setSelectedFile(null); }}
              disabled={isLoading}
              className="px-2.5 py-1 text-xs font-medium text-white bg-kira-600 rounded-lg hover:bg-kira-700 disabled:opacity-50"
            >
              {isLoading ? '업로드 중...' : '업로드'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
