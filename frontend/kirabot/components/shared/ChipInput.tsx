import React, { useState, useRef, KeyboardEvent, CompositionEvent, ClipboardEvent } from 'react';
import { X } from 'lucide-react';

interface ChipInputProps {
  label: string;
  chips: string[];
  onChange: (chips: string[]) => void;
  placeholder?: string;
}

const ChipInput: React.FC<ChipInputProps> = ({ label, chips, onChange, placeholder = '입력 후 Enter (쉼표로 구분 가능)' }) => {
  const [input, setInput] = useState('');
  const composingRef = useRef(false);

  /** 쉼표로 분리하여 여러 칩 추가 */
  const addChips = (raw: string) => {
    const parts = raw.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    if (parts.length === 0) return;
    const unique = parts.filter(p => !chips.includes(p));
    // 중복 제거 (parts 내부에서도)
    const deduped = [...new Set(unique)];
    if (deduped.length > 0) {
      onChange([...chips, ...deduped]);
    }
    setInput('');
  };

  const removeChip = (chip: string) => onChange(chips.filter(c => c !== chip));

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (composingRef.current) return; // IME 조합 중이면 무시
    if (e.key === 'Enter') { e.preventDefault(); addChips(input); }
    if (e.key === 'Backspace' && !input && chips.length > 0) {
      onChange(chips.slice(0, -1));
    }
  };

  const handleCompositionStart = (_e: CompositionEvent) => { composingRef.current = true; };
  const handleCompositionEnd = (_e: CompositionEvent) => { composingRef.current = false; };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text');
    if (pasted.includes(',') || pasted.includes('，')) {
      e.preventDefault();
      addChips(pasted);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    // 타이핑 중 쉼표가 들어오면 즉시 분리
    if (!composingRef.current && (val.includes(',') || val.includes('，'))) {
      addChips(val);
    } else {
      setInput(val);
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      <div className="flex flex-wrap gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 focus-within:border-kira-500 focus-within:ring-2 focus-within:ring-kira-200">
        {chips.map(chip => (
          <span key={chip} className="inline-flex items-center gap-1 rounded-full bg-kira-100 px-2.5 py-0.5 text-xs font-medium text-kira-700">
            {chip}
            <button type="button" onClick={() => removeChip(chip)} className="hover:text-kira-900">
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onCompositionStart={handleCompositionStart}
          onCompositionEnd={handleCompositionEnd}
          onPaste={handlePaste}
          onBlur={() => addChips(input)}
          placeholder={chips.length === 0 ? placeholder : ''}
          className="flex-1 min-w-[100px] text-sm outline-none bg-transparent"
        />
      </div>
    </div>
  );
};

export default ChipInput;
