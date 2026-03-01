import React from 'react';
import { X, RotateCcw, Clock } from 'lucide-react';
import type { ProfileVersion } from '../../../types';

interface Props {
  versions: ProfileVersion[];
  onRollback: (version: number) => void;
  onClose: () => void;
}

export default function VersionHistory({ versions, onRollback, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h3 className="text-base font-semibold text-slate-800">버전 이력</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto p-4 space-y-2">
          {versions.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">버전 이력이 없습니다.</p>
          ) : (
            versions.slice().reverse().map((v) => (
              <div key={v.version} className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3 hover:bg-slate-50">
                <div className="flex items-center gap-3">
                  <Clock size={14} className="text-slate-400" />
                  <div>
                    <span className="text-sm font-medium text-slate-700">v{v.version}</span>
                    <span className="ml-2 text-xs text-slate-400">{v.date}</span>
                    {v.reason && <p className="text-xs text-slate-500 mt-0.5">{v.reason}</p>}
                  </div>
                </div>
                <button
                  onClick={() => onRollback(v.version)}
                  className="flex items-center gap-1 text-xs text-kira-600 hover:text-kira-700"
                >
                  <RotateCcw size={12} /> 되돌리기
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
