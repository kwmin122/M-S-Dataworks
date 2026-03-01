import React, { useState, useCallback, useRef } from 'react';
import { ChevronDown, ChevronUp, Plus, Trash2, X } from 'lucide-react';
import ChipInput from '../shared/ChipInput';
import type { AlertRule } from '../../services/kiraApiService';

interface AlertFilterSectionProps {
  rules: AlertRule[];
  onAddRule: () => void;
  onUpdateRule: (index: number, rule: AlertRule) => void;
  onDeleteRule: (index: number) => void;
}

const hasInvalidAmountRange = (rule: AlertRule): boolean => {
  return !!(rule.minAmt && rule.maxAmt && rule.minAmt > rule.maxAmt);
};

export const AlertFilterSection: React.FC<AlertFilterSectionProps> = ({
  rules,
  onAddRule,
  onUpdateRule,
  onDeleteRule,
}) => {
  const [expandedRules, setExpandedRules] = useState<Set<number>>(new Set([0]));
  const [keywordInputs, setKeywordInputs] = useState<Record<number, string>>({});
  const composingRefs = useRef<Record<number, boolean>>({});

  const toggleRule = useCallback((index: number) => {
    setExpandedRules((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  const updateRule = useCallback((index: number, field: keyof AlertRule, value: any) => {
    const updated = { ...rules[index], [field]: value };
    onUpdateRule(index, updated);
  }, [rules, onUpdateRule]);

  const getKeywordPreview = (rule: AlertRule): string => {
    if (rule.keywords.length === 0) return '키워드 없음';
    if (rule.keywords.length === 1) return rule.keywords[0];
    return `${rule.keywords[0]}, ${rule.keywords[1]}${rule.keywords.length > 2 ? ` 외 ${rule.keywords.length - 2}개` : ''}`;
  };

  const addKeywords = useCallback((index: number, raw: string) => {
    if (!raw.trim()) return;
    const rule = rules[index];
    const parts = raw.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    if (parts.length === 0) return;
    const unique = parts.filter(p => !rule.keywords.includes(p));
    const deduped = [...new Set(unique)];
    if (deduped.length > 0) {
      updateRule(index, 'keywords', [...rule.keywords, ...deduped]);
    }
    setKeywordInputs(prev => ({ ...prev, [index]: '' }));
  }, [rules, updateRule]);

  const removeKeyword = useCallback((index: number, chip: string) => {
    const rule = rules[index];
    updateRule(index, 'keywords', rule.keywords.filter(c => c !== chip));
  }, [rules, updateRule]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-700">필터 규칙</h2>
        <button
          type="button"
          onClick={onAddRule}
          className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
        >
          <Plus size={16} />
          규칙 추가
        </button>
      </div>

      {rules.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
          <p className="text-sm text-slate-500">
            규칙을 추가하여 원하는 공고만 받아보세요
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {rules.map((rule, index) => {
            const isExpanded = expandedRules.has(index);
            return (
              <div
                key={rule.id}
                className="rounded-lg border border-slate-200 bg-white overflow-hidden"
              >
                {/* Rule Header */}
                <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
                  <button
                    type="button"
                    onClick={() => toggleRule(index)}
                    className="flex items-center gap-2 flex-1 text-left"
                    aria-expanded={isExpanded}
                  >
                    {isExpanded ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
                    <span className="text-sm font-medium text-slate-700">
                      규칙 #{index + 1}
                    </span>
                    <span className="text-xs text-slate-500">
                      {getKeywordPreview(rule)}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteRule(index)}
                    className="p-1 text-slate-400 hover:text-red-600"
                    title="규칙 삭제"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                {/* Rule Fields (Expanded) */}
                {isExpanded && (
                  <div className="p-4 space-y-4">
                    {/* Keywords (Required) */}
                    <div>
                      <div className="flex items-baseline gap-1 mb-1">
                        <label className="block text-sm font-medium text-slate-700">
                          포함 키워드
                        </label>
                        <span className="text-red-500 text-sm">*</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 focus-within:border-kira-500 focus-within:ring-2 focus-within:ring-kira-200">
                        {rule.keywords.map(chip => (
                          <span key={chip} className="inline-flex items-center gap-1 rounded-full bg-kira-100 px-2.5 py-0.5 text-xs font-medium text-kira-700">
                            {chip}
                            <button
                              type="button"
                              onClick={() => removeKeyword(index, chip)}
                              className="rounded-full p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
                            >
                              <X size={12} />
                            </button>
                          </span>
                        ))}
                        <input
                          type="text"
                          value={keywordInputs[index] || ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            if (!composingRefs.current[index] && (val.includes(',') || val.includes('，'))) {
                              addKeywords(index, val);
                            } else {
                              setKeywordInputs(prev => ({ ...prev, [index]: val }));
                            }
                          }}
                          onKeyDown={(e) => {
                            if (composingRefs.current[index]) return;
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              addKeywords(index, keywordInputs[index] || '');
                            }
                            if (e.key === 'Backspace' && !(keywordInputs[index] || '') && rule.keywords.length > 0) {
                              updateRule(index, 'keywords', rule.keywords.slice(0, -1));
                            }
                          }}
                          onCompositionStart={() => { composingRefs.current[index] = true; }}
                          onCompositionEnd={() => { composingRefs.current[index] = false; }}
                          onPaste={(e) => {
                            const pasted = e.clipboardData.getData('text');
                            if (pasted.includes(',') || pasted.includes('，')) {
                              e.preventDefault();
                              addKeywords(index, pasted);
                            }
                          }}
                          onBlur={() => addKeywords(index, keywordInputs[index] || '')}
                          placeholder={rule.keywords.length === 0 ? '입력 후 Enter (쉼표로 구분 가능)' : ''}
                          className="flex-1 min-w-[100px] text-sm outline-none bg-transparent"
                        />
                      </div>
                    </div>

                    {/* Exclude Keywords */}
                    <ChipInput
                      label="제외 키워드"
                      chips={rule.excludeKeywords}
                      onChange={(value) => updateRule(index, 'excludeKeywords', value)}
                      placeholder="유지보수, 임대"
                    />

                    {/* Regions */}
                    <ChipInput
                      label="포함 지역"
                      chips={rule.regions}
                      onChange={(value) => updateRule(index, 'regions', value)}
                      placeholder="서울, 경기"
                    />

                    {/* Exclude Regions */}
                    <ChipInput
                      label="🚫 제외 지역"
                      chips={rule.excludeRegions || []}
                      onChange={(value) => updateRule(index, 'excludeRegions', value)}
                      placeholder="부산, 제주"
                    />

                    {/* Product Codes */}
                    <ChipInput
                      label="물품분류번호"
                      chips={rule.productCodes || []}
                      onChange={(value) => updateRule(index, 'productCodes', value)}
                      placeholder="42101, 42105"
                    />

                    {/* Detailed Items */}
                    <ChipInput
                      label="세부품명"
                      chips={rule.detailedItems || []}
                      onChange={(value) => updateRule(index, 'detailedItems', value)}
                      placeholder="교통신호등, CCTV카메라"
                    />

                    {/* Amount Range */}
                    <div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">
                            최소 금액 (만원)
                          </label>
                          <input
                            type="number"
                            value={rule.minAmt ?? ''}
                            onChange={(e) => {
                              const val = parseInt(e.target.value, 10);
                              updateRule(index, 'minAmt', (!isNaN(val) && val >= 0) ? val : undefined);
                            }}
                            placeholder="1000"
                            min="0"
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">
                            최대 금액 (만원)
                          </label>
                          <input
                            type="number"
                            value={rule.maxAmt ?? ''}
                            onChange={(e) => {
                              const val = parseInt(e.target.value, 10);
                              updateRule(index, 'maxAmt', (!isNaN(val) && val >= 0) ? val : undefined);
                            }}
                            placeholder="5000"
                            min="0"
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                          />
                        </div>
                      </div>
                      {hasInvalidAmountRange(rule) && (
                        <p className="text-xs text-red-600 mt-1">
                          ⚠️ 최소 금액이 최대 금액보다 큽니다
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AlertFilterSection;
