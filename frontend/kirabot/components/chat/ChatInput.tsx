import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Building2, FileSearch } from 'lucide-react';
import { useAutoResize } from '../../hooks/useAutoResize';
import { useChatContext } from '../../context/ChatContext';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import type { MessageAction } from '../../types';

const defaultQuestions = [
  '우리 회사 이름과 핵심 역량을 문서 근거로 알려줘',
  '핵심 요건 3개만 먼저 요약해줘',
  '미충족 요건 준비 순서를 알려줘',
  '마감 전 체크리스트를 만들어줘',
];

interface Props {
  onSendText: (text: string) => void;
  onAction?: (action: MessageAction) => void;
}

const ChatInput: React.FC<Props> = ({ onSendText, onAction }) => {
  const [text, setText] = useState('');
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const textareaRef = useAutoResize(text);
  const { state } = useChatContext();
  const { conversation } = useActiveConversation();

  const showSuggestions = conversation?.phase === 'doc_chat';

  // 메뉴 외부 클릭 시 닫기
  useEffect(() => {
    if (!showUploadMenu) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowUploadMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showUploadMenu]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || state.isProcessing) return;
    onSendText(trimmed);
    setText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleUploadOption = (actionType: 'header_add_company' | 'header_upload_target') => {
    setShowUploadMenu(false);
    if (onAction) {
      onAction({ type: actionType });
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white p-3">
      {showSuggestions && (
        <div className="mb-2 flex flex-wrap gap-2">
          {defaultQuestions.map((q) => (
            <button
              key={q}
              type="button"
              className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100"
              onClick={() => onSendText(q)}
            >
              {q}
            </button>
          ))}
        </div>
      )}
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <div className="flex flex-1 items-end rounded-xl border border-slate-300 bg-white px-3 py-2 focus-within:border-kira-500 focus-within:ring-2 focus-within:ring-kira-200">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="메시지를 입력하세요"
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-slate-400"
            style={{ maxHeight: '200px' }}
          />
          {/* 파일 업로드 버튼 + 드롭다운 */}
          <div className="relative ml-2" ref={menuRef}>
            <button
              type="button"
              onClick={() => setShowUploadMenu(!showUploadMenu)}
              className="shrink-0 text-slate-400 hover:text-slate-600 transition-colors"
              title="파일 업로드"
            >
              <Paperclip size={18} />
            </button>
            {showUploadMenu && (
              <div className="absolute bottom-full right-0 mb-2 w-48 rounded-lg border border-slate-200 bg-white py-1 shadow-lg z-50">
                <button
                  type="button"
                  onClick={() => handleUploadOption('header_add_company')}
                  className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Building2 size={16} className="text-kira-500" />
                  회사 문서 업로드
                </button>
                <button
                  type="button"
                  onClick={() => handleUploadOption('header_upload_target')}
                  className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <FileSearch size={16} className="text-emerald-500" />
                  분석할 공고 업로드
                </button>
              </div>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={handleSend}
          disabled={!text.trim() || state.isProcessing}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-kira-700 text-white hover:bg-kira-800 disabled:opacity-50"
          aria-label="메시지 전송"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
