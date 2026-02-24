import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Building2, FileSearch, Search, FileText, Bell } from 'lucide-react';
import { useAutoResize } from '../../hooks/useAutoResize';
import { useChatContext } from '../../context/ChatContext';
import type { MessageAction, User } from '../../types';

interface WelcomeScreenProps {
  user: User | null;
  onSendText: (text: string) => void;
  onAction: (action: MessageAction) => void;
}

const chips = [
  { label: '공고 검색/분석', value: 'bid_search', icon: Search },
  { label: '일반 문서 분석', value: 'doc_analysis', icon: FileText },
  { label: '공고 알림 설정', value: 'setup_alert', icon: Bell },
] as const;

const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ user, onSendText, onAction }) => {
  const [text, setText] = useState('');
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const textareaRef = useAutoResize(text);
  const { state } = useChatContext();

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
    // 한글 IME 조합 중 Enter 무시 (이중 입력 방지)
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleUploadOption = (actionType: 'header_add_company' | 'header_upload_target') => {
    setShowUploadMenu(false);
    onAction({ type: actionType });
  };

  const displayName = user?.name || '사용자';

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4">
      <div className="w-full max-w-2xl text-center">
        {/* Greeting */}
        <h1 className="text-3xl font-bold text-slate-800">
          안녕하세요, {displayName}님
        </h1>
        <p className="mt-2 text-base text-slate-500">
          무엇을 도와드릴까요?
        </p>

        {/* Input */}
        <div className="mt-8 flex items-end gap-2">
          <div className="flex flex-1 items-end rounded-2xl border border-slate-300 bg-white px-4 py-3 shadow-sm focus-within:border-kira-500 focus-within:ring-2 focus-within:ring-kira-200 focus-within:shadow-md transition-shadow">
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="질문이나 공고 키워드를 입력하세요..."
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-slate-400"
              style={{ maxHeight: '120px' }}
            />
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
            className="flex h-11 w-11 items-center justify-center rounded-2xl bg-kira-700 text-white hover:bg-kira-800 disabled:opacity-50 transition-colors"
            aria-label="메시지 전송"
          >
            <Send size={18} />
          </button>
        </div>

        {/* Chip buttons */}
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          {chips.map(({ label, value, icon: Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => onAction({ type: 'welcome_action', value })}
              className="flex items-center gap-2 rounded-full border border-kira-200 bg-kira-50 px-4 py-2 text-sm text-kira-700 shadow-sm hover:bg-kira-100 hover:shadow-md transition-colors"
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default WelcomeScreen;
