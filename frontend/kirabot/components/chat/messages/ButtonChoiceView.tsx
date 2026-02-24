import React from 'react';
import type { ButtonChoiceMessage, MessageAction } from '../../../types';

interface Props {
  message: ButtonChoiceMessage;
  onAction: (action: MessageAction) => void;
}

const ButtonChoiceView: React.FC<Props> = ({ message, onAction }) => {
  const isSelected = Boolean(message.selectedValue);

  return (
    <div>
      <p className="mb-3 whitespace-pre-line">{message.text}</p>
      <div className="flex flex-wrap gap-2">
        {message.choices.map((choice) => {
          const isChosen = message.selectedValue === choice.value;
          return (
            <button
              key={choice.value}
              type="button"
              disabled={isSelected}
              onClick={() =>
                onAction({
                  type: 'choice_selected',
                  value: choice.value,
                  messageId: message.id,
                })
              }
              className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-all ${
                isChosen
                  ? 'border-kira-600 bg-kira-600 text-white'
                  : isSelected
                    ? 'border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-kira-400 hover:bg-kira-50'
              }`}
            >
              {choice.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default ButtonChoiceView;
