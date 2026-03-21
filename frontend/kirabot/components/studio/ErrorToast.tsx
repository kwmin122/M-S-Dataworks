import React, { useEffect, useState, useCallback } from 'react';
import { AlertCircle, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  text: string;
}

interface ErrorToastProps {
  messages: ToastMessage[];
  onDismiss: (id: string) => void;
  /** Auto-dismiss delay in ms. Default 5000. Set 0 to disable. */
  autoDismissMs?: number;
}

/**
 * Renders a stack of error toast notifications that auto-dismiss after 5 seconds.
 * Place at StudioProject level; pass messages down via context or props.
 */
export default function ErrorToast({
  messages,
  onDismiss,
  autoDismissMs = 5000,
}: ErrorToastProps) {
  if (messages.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {messages.map((msg) => (
        <ToastItem
          key={msg.id}
          message={msg}
          onDismiss={onDismiss}
          autoDismissMs={autoDismissMs}
        />
      ))}
    </div>
  );
}

function ToastItem({
  message,
  onDismiss,
  autoDismissMs,
}: {
  message: ToastMessage;
  onDismiss: (id: string) => void;
  autoDismissMs: number;
}) {
  const [visible, setVisible] = useState(true);

  const dismiss = useCallback(() => {
    setVisible(false);
    // Wait for CSS transition before removing from list
    setTimeout(() => onDismiss(message.id), 200);
  }, [message.id, onDismiss]);

  useEffect(() => {
    if (autoDismissMs <= 0) return;
    const timer = setTimeout(dismiss, autoDismissMs);
    return () => clearTimeout(timer);
  }, [autoDismissMs, dismiss]);

  return (
    <div
      className={`flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 shadow-lg transition-all duration-200 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      }`}
      role="alert"
    >
      <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
      <p className="text-sm text-red-700 flex-1">{message.text}</p>
      <button
        onClick={dismiss}
        className="text-red-400 hover:text-red-600 shrink-0"
        aria-label="닫기"
      >
        <X size={14} />
      </button>
    </div>
  );
}

/** Helper: generate a unique toast id */
let _toastSeq = 0;
export function makeToastId(): string {
  return `toast-${Date.now()}-${++_toastSeq}`;
}
