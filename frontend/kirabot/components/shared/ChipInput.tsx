import React, { useState, KeyboardEvent } from 'react';
import { X } from 'lucide-react';

interface ChipInputProps {
  label: string;
  chips: string[];
  onChange: (chips: string[]) => void;
  placeholder?: string;
}

const ChipInput: React.FC<ChipInputProps> = ({ label, chips, onChange, placeholder = '입력 후 Enter' }) => {
  const [input, setInput] = useState('');

  const addChip = () => {
    const trimmed = input.trim();
    if (trimmed && !chips.includes(trimmed)) {
      onChange([...chips, trimmed]);
    }
    setInput('');
  };

  const removeChip = (chip: string) => onChange(chips.filter(c => c !== chip));

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') { e.preventDefault(); addChip(); }
    if (e.key === 'Backspace' && !input && chips.length > 0) {
      onChange(chips.slice(0, -1));
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
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={addChip}
          placeholder={chips.length === 0 ? placeholder : ''}
          className="flex-1 min-w-[100px] text-sm outline-none bg-transparent"
        />
      </div>
    </div>
  );
};

export default ChipInput;
