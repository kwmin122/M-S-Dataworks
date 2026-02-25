import React, { useCallback, useRef, useState } from 'react';
import { UploadCloud, CheckCircle2, File as FileIcon } from 'lucide-react';
import type { FileUploadMessage, MessageAction } from '../../../types';

interface Props {
  message: FileUploadMessage;
  onAction: (action: MessageAction) => void;
}

const FileUploadView: React.FC<Props> = ({ message, onAction }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const isUploaded = Boolean(message.uploadedFileNames?.length);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0 || isUploaded) return;
      onAction({
        type: 'files_uploaded',
        files: Array.from(files),
        messageId: message.id,
      });
    },
    [message.id, onAction, isUploaded],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  if (isUploaded) {
    return (
      <div>
        <p className="mb-2 whitespace-pre-line text-sm">{message.text}</p>
        <div className="space-y-1">
          {message.uploadedFileNames!.map((name) => (
            <div
              key={name}
              className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs"
            >
              <CheckCircle2 size={14} className="text-emerald-600" />
              <span className="truncate text-slate-700">{name}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <p className="mb-2 whitespace-pre-line text-sm">{message.text}</p>
      <div
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors ${
          dragOver ? 'border-primary-400 bg-primary-50' : 'border-slate-300 bg-slate-50'
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <UploadCloud size={32} className="mb-2 text-slate-400" />
        <p className="text-xs text-slate-500 mb-2">파일을 드래그하거나 클릭하여 선택</p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-100"
        >
          <FileIcon size={12} className="mr-1 inline" />
          파일 선택
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={message.accept}
          multiple={message.multiple}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
    </div>
  );
};

export default FileUploadView;
