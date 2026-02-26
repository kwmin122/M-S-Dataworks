import React, { useState } from 'react';
import type { InlineFormMessage, MessageAction } from '../../../types';

interface Props {
  message: InlineFormMessage;
  onAction: (action: MessageAction) => void;
}

const InlineFormView: React.FC<Props> = ({ message, onAction }) => {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const field of message.fields) {
      init[field.key] = '';
    }
    return init;
  });

  const isSubmitted = Boolean(message.submittedValues);
  const displayValues = message.submittedValues ?? values;

  const handleSubmit = () => {
    onAction({ type: 'form_submitted', values, messageId: message.id });
  };

  return (
    <div>
      <p className="mb-3 whitespace-pre-line text-sm">{message.text}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-2">
        {message.fields.map((field) => (
          <div key={field.key} className={field.type === 'text' && !field.options ? 'sm:col-span-2' : field.type === 'multiselect' ? 'sm:col-span-2' : ''}>
            <label className="block text-xs font-semibold text-slate-600 mb-1">{field.label}</label>
            {field.type === 'multiselect' && field.options ? (
              <div className="flex flex-wrap gap-1.5">
                {field.options.map((opt) => {
                  const selected = (displayValues[field.key] || '').split(',').filter(Boolean);
                  const isActive = selected.includes(opt);
                  return (
                    <button
                      key={opt}
                      type="button"
                      disabled={isSubmitted}
                      onClick={() => {
                        const current = (values[field.key] || '').split(',').filter(Boolean);
                        const next = isActive ? current.filter(v => v !== opt) : [...current, opt];
                        setValues((prev) => ({ ...prev, [field.key]: next.join(',') }));
                      }}
                      className={`rounded-full px-2.5 py-1 text-xs font-medium border transition-colors disabled:opacity-60 ${
                        isActive
                          ? 'border-primary-600 bg-primary-600 text-white'
                          : 'border-slate-300 text-slate-600 hover:border-primary-400 hover:bg-primary-50'
                      }`}
                    >
                      {opt}
                    </button>
                  );
                })}
                {!isSubmitted && (displayValues[field.key] || '').split(',').filter(Boolean).length === 0 && (
                  <span className="text-xs text-slate-400 self-center">선택 안하면 전체</span>
                )}
              </div>
            ) : field.type === 'select' && field.options ? (
              <select
                value={displayValues[field.key] || ''}
                disabled={isSubmitted}
                onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                className="w-full h-8 rounded-lg border border-slate-300 px-2 text-xs outline-none focus:border-primary-500 disabled:bg-slate-100"
              >
                <option value="">선택</option>
                {field.options.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            ) : (
              <input
                type={field.type === 'number' ? 'number' : 'text'}
                value={displayValues[field.key] || ''}
                disabled={isSubmitted}
                onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                placeholder={field.label}
                className="w-full h-8 rounded-lg border border-slate-300 px-2 text-xs outline-none focus:border-primary-500 disabled:bg-slate-100"
              />
            )}
          </div>
        ))}
      </div>
      {!isSubmitted && (
        <button
          type="button"
          onClick={handleSubmit}
          className="mt-3 w-full rounded-lg bg-primary-700 px-4 py-2 text-sm font-medium text-white hover:bg-primary-800"
        >
          {message.submitLabel}
        </button>
      )}
      {isSubmitted && (
        <p className="mt-2 text-xs text-slate-400">제출 완료</p>
      )}
    </div>
  );
};

export default InlineFormView;
