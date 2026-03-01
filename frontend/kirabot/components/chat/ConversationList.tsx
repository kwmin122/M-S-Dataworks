import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, Trash2, Pencil } from 'lucide-react';
import type { Conversation } from '../../types';

interface ConversationListProps {
  conversations: Conversation[];
  activeId: string | null;
  collapsed: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename?: (id: string, newTitle: string) => void;
}

const ConversationList: React.FC<ConversationListProps> = ({
  conversations,
  activeId,
  collapsed,
  onSelect,
  onDelete,
  onRename,
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const startEditing = (conv: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditValue(conv.title);
  };

  const commitEdit = () => {
    if (editingId && editValue.trim() && onRename) {
      onRename(editingId, editValue.trim());
    }
    setEditingId(null);
  };

  if (collapsed) {
    return (
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {conversations.map((conv) => (
          <button
            key={conv.id}
            type="button"
            onClick={() => onSelect(conv.id)}
            className={`flex h-9 w-9 items-center justify-center rounded-lg ${
              conv.id === activeId ? 'bg-sidebar-hover text-white' : 'text-slate-400 hover:bg-white/5 hover:text-white'
            }`}
            title={conv.title}
          >
            <MessageSquare size={16} />
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
      {conversations.map((conv) => (
        <button
          type="button"
          key={conv.id}
          className={`group flex w-full items-center gap-2 rounded-lg px-3 py-2 cursor-pointer text-left ${
            conv.id === activeId ? 'bg-sidebar-hover text-white' : 'text-slate-300 hover:bg-white/5 hover:text-white'
          }`}
          aria-current={conv.id === activeId ? 'true' : undefined}
          onClick={() => onSelect(conv.id)}
        >
          <MessageSquare size={14} className="shrink-0" />
          {editingId === conv.id ? (
            <input
              ref={inputRef}
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitEdit();
                if (e.key === 'Escape') setEditingId(null);
              }}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 bg-sidebar-hover text-white text-sm rounded px-1 py-0 outline-none border border-white/10 focus:border-primary-400"
            />
          ) : (
            <span className="flex-1 truncate text-sm">{conv.title.slice(0, 20)}</span>
          )}
          <div className="hidden shrink-0 gap-0.5 group-hover:flex">
            <button
              type="button"
              onClick={(e) => startEditing(conv, e)}
              className="rounded p-1 text-slate-500 hover:text-primary-400"
              title="이름 변경"
            >
              <Pencil size={13} />
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              className="rounded p-1 text-slate-500 hover:text-red-400"
              title="삭제"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </button>
      ))}
      {conversations.length === 0 && (
        <p className="px-3 py-6 text-center text-xs text-slate-500">대화가 없습니다</p>
      )}
    </div>
  );
};

export default ConversationList;
