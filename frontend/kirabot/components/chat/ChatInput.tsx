import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Send, Paperclip, Building2, FileSearch, X } from 'lucide-react';
import { useAutoResize } from '../../hooks/useAutoResize';
import { useChatContext } from '../../context/ChatContext';
import { useActiveConversation } from '../../hooks/useActiveConversation';
import type { MessageAction, DocMention } from '../../types';

const defaultQuestions = [
  '우리 회사 이름과 핵심 역량을 문서 근거로 알려줘',
  '핵심 요건 3개만 먼저 요약해줘',
  '미충족 요건 준비 순서를 알려줘',
  '마감 전 체크리스트를 만들어줘',
];

interface Props {
  onSendText: (text: string, sourceFiles?: string[]) => void;
  onAction?: (action: MessageAction) => void;
}

const ChatInput: React.FC<Props> = ({ onSendText, onAction }) => {
  const [text, setText] = useState('');
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionIndex, setMentionIndex] = useState(0);
  const [docTags, setDocTags] = useState<DocMention[]>([]);
  const menuRef = useRef<HTMLDivElement>(null);
  const mentionRef = useRef<HTMLDivElement>(null);
  const textareaRef = useAutoResize(text);
  const { state } = useChatContext();
  const { conversation } = useActiveConversation();

  const showSuggestions = conversation?.phase === 'doc_chat';

  // Build available document list (memoized to prevent infinite re-render in useEffect)
  const allDocs: DocMention[] = useMemo(() => [
    ...(conversation?.companyDocuments || []).map(d => ({
      sourceFile: d.source_file,
      label: d.source_file,
      type: 'company' as const,
    })),
    ...(conversation?.uploadedFileName ? [{
      sourceFile: conversation.uploadedFileName,
      label: conversation.uploadedFileName,
      type: 'rfx' as const,
    }] : []),
  ], [conversation?.companyDocuments, conversation?.uploadedFileName]);

  const filteredDocs = mentionQuery
    ? allDocs.filter(d => d.label.toLowerCase().includes(mentionQuery.toLowerCase()))
    : allDocs;

  const mentionOptions: DocMention[] = [
    ...filteredDocs,
    ...(allDocs.length > 1 ? [{ sourceFile: '*', label: '전체 문서 비교', type: 'company' as const }] : []),
  ];

  // Auto-populate docTags when activeDocFilter is set (from CompanyDocCard ask button)
  useEffect(() => {
    if (conversation?.activeDocFilter?.length) {
      const tags: DocMention[] = conversation.activeDocFilter.map(sf => {
        const found = allDocs.find(d => d.sourceFile === sf);
        return found || { sourceFile: sf, label: sf, type: 'company' as const };
      });
      setDocTags(tags);
      textareaRef.current?.focus();
    }
  }, [conversation?.activeDocFilter, allDocs]);

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

  // 멘션 드롭다운 외부 클릭 시 닫기
  useEffect(() => {
    if (!mentionOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (mentionRef.current && !mentionRef.current.contains(e.target as Node)) {
        setMentionOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [mentionOpen]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && docTags.length === 0) return;
    if (state.isProcessing) return;
    const sourceFiles = docTags.length > 0 ? docTags.map(t => t.sourceFile) : undefined;
    onSendText(trimmed, sourceFiles);
    setText('');
    setDocTags([]);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setText(value);

    const lastAt = value.lastIndexOf('@');
    if (lastAt >= 0 && allDocs.length > 0) {
      const afterAt = value.slice(lastAt + 1);
      if (!afterAt.includes(' ') && !afterAt.includes('\n')) {
        setMentionOpen(true);
        setMentionQuery(afterAt);
        setMentionIndex(0);
        return;
      }
    }
    setMentionOpen(false);
  };

  const handleMentionSelect = (doc: DocMention) => {
    const lastAt = text.lastIndexOf('@');
    const before = lastAt >= 0 ? text.slice(0, lastAt) : text;
    setDocTags(prev => {
      if (prev.some(t => t.sourceFile === doc.sourceFile)) return prev;
      return [...prev, doc];
    });
    setText(before);
    setMentionOpen(false);
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // 멘션 드롭다운 키보드 네비게이션
    if (mentionOpen && mentionOptions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex(prev => Math.min(prev + 1, mentionOptions.length - 1));
        return;
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex(prev => Math.max(prev - 1, 0));
        return;
      } else if (e.key === 'Enter') {
        e.preventDefault();
        handleMentionSelect(mentionOptions[mentionIndex]);
        return;
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setMentionOpen(false);
        return;
      }
    }
    // 한글 IME 조합 중 Enter 무시 (이중 입력 방지)
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
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
      {/* Doc tag chips */}
      {docTags.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5 px-1">
          {docTags.map((tag, i) => (
            <span key={tag.sourceFile} className="inline-flex items-center gap-1 rounded-full bg-kira-100 text-kira-700 px-2.5 py-0.5 text-xs font-medium">
              <span className="text-[10px]">{tag.type === 'company' ? '\u{1F3E2}' : '\u{1F4CB}'}</span>
              @{tag.label}
              <button type="button" onClick={() => setDocTags(prev => prev.filter((_, j) => j !== i))}
                className="ml-0.5 text-kira-400 hover:text-kira-600 transition-colors">
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <div className="relative flex flex-1 items-end rounded-xl border border-slate-300 bg-white px-3 py-2 focus-within:border-kira-500 focus-within:ring-2 focus-within:ring-kira-200">
          {/* Mention autocomplete dropdown */}
          {mentionOpen && mentionOptions.length > 0 && (
            <div ref={mentionRef} className="absolute bottom-full left-0 right-0 mb-1 rounded-xl border border-slate-200 bg-white shadow-lg overflow-hidden z-50 max-h-48 overflow-y-auto">
              <div className="px-3 py-1.5 text-[11px] font-medium text-slate-400 border-b border-slate-100">
                문서 선택
              </div>
              {mentionOptions.map((doc, i) => (
                <button
                  key={doc.sourceFile}
                  type="button"
                  onMouseDown={(e) => { e.preventDefault(); handleMentionSelect(doc); }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors ${
                    i === mentionIndex ? 'bg-kira-50 text-kira-700' : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <span className="text-xs">{doc.sourceFile === '*' ? '\u{1F504}' : doc.type === 'company' ? '\u{1F3E2}' : '\u{1F4CB}'}</span>
                  <span className="flex-1 truncate">{doc.label}</span>
                </button>
              ))}
            </div>
          )}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={handleInputChange}
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
          disabled={(!text.trim() && docTags.length === 0) || state.isProcessing}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-kira-700 text-white hover:bg-kira-800 disabled:opacity-50"
          aria-label="메시지 전송"
        >
          <Send size={18} />
        </button>
      </div>
      <p className="mt-1.5 text-center text-[11px] text-slate-400">
        Kira는 실수할 수 있습니다. 중요한 정보는 반드시 원문을 확인하세요.
      </p>
    </div>
  );
};

export default ChatInput;
