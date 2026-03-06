import React, { useState, useEffect } from 'react';
import { X, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { LearnedPattern } from '../../types';
import * as kiraApi from '../../services/kiraApiService';

interface PendingKnowledgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  companyId: string;
  docType?: string;
}

const PendingKnowledgeModal: React.FC<PendingKnowledgeModalProps> = ({
  isOpen,
  onClose,
  companyId,
  docType = 'proposal',
}) => {
  const [patterns, setPatterns] = useState<LearnedPattern[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processingKeys, setProcessingKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (isOpen) {
      loadPatterns();
    }
  }, [isOpen, companyId, docType]);

  const loadPatterns = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await kiraApi.getPendingKnowledge(companyId, docType);
      setPatterns(data.patterns || []);
    } catch (err) {
      console.error('Failed to load pending knowledge:', err);
      setError('학습 제안 목록을 불러오는 데 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprove = async (patternKey: string) => {
    setProcessingKeys(prev => new Set(prev).add(patternKey));
    try {
      await kiraApi.approveKnowledge(companyId, patternKey, docType);
      setPatterns(prev => prev.filter(p => p.pattern_key !== patternKey));
    } catch (err) {
      console.error('Failed to approve knowledge:', err);
      setError('학습 승인에 실패했습니다.');
    } finally {
      setProcessingKeys(prev => {
        const next = new Set(prev);
        next.delete(patternKey);
        return next;
      });
    }
  };

  const handleReject = async (patternKey: string) => {
    setProcessingKeys(prev => new Set(prev).add(patternKey));
    try {
      await kiraApi.rejectKnowledge(companyId, patternKey, docType);
      setPatterns(prev => prev.filter(p => p.pattern_key !== patternKey));
    } catch (err) {
      console.error('Failed to reject knowledge:', err);
      setError('학습 거부에 실패했습니다.');
    } finally {
      setProcessingKeys(prev => {
        const next = new Set(prev);
        next.delete(patternKey);
        return next;
      });
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900">학습 제안</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading && (
            <div className="text-center py-8 text-gray-500">
              학습 제안 목록을 불러오는 중...
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
              {error}
            </div>
          )}

          {!isLoading && !error && patterns.length === 0 && (
            <div className="text-center py-12">
              <AlertCircle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-lg">대기 중인 학습 제안이 없습니다.</p>
              <p className="text-gray-400 text-sm mt-2">
                문서 수정 시 반복 패턴이 감지되면 여기에 표시됩니다.
              </p>
            </div>
          )}

          {!isLoading && !error && patterns.length > 0 && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600 mb-4">
                아래 수정 패턴을 학습하면 다음 생성 시 자동으로 반영됩니다.
              </p>
              {patterns.map((pattern) => (
                <div
                  key={pattern.pattern_key}
                  className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900 mb-1">
                        {pattern.section_name}
                      </h3>
                      <p className="text-sm text-gray-600 mb-2">
                        {pattern.description}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <span className="px-2 py-1 bg-gray-100 rounded">
                          {pattern.diff_type === 'replace' && '수정'}
                          {pattern.diff_type === 'delete' && '삭제'}
                          {pattern.diff_type === 'insert' && '추가'}
                        </span>
                        <span>·</span>
                        <span>{pattern.occurrence_count}회 반복</span>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="bg-red-50 border border-red-200 rounded p-3">
                      <p className="text-xs font-semibold text-red-800 mb-1">
                        AI 생성 (원본)
                      </p>
                      <p className="text-sm text-gray-700 line-clamp-3">
                        {pattern.original_example}
                      </p>
                    </div>
                    <div className="bg-green-50 border border-green-200 rounded p-3">
                      <p className="text-xs font-semibold text-green-800 mb-1">
                        사용자 수정 (변경)
                      </p>
                      <p className="text-sm text-gray-700 line-clamp-3">
                        {pattern.edited_example}
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleApprove(pattern.pattern_key)}
                      disabled={processingKeys.has(pattern.pattern_key)}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>학습 승인</span>
                    </button>
                    <button
                      onClick={() => handleReject(pattern.pattern_key)}
                      disabled={processingKeys.has(pattern.pattern_key)}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <XCircle className="w-4 h-4" />
                      <span>거부</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
};

export default PendingKnowledgeModal;
