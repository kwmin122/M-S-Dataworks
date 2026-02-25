import React from 'react';
import { FileX, Quote } from 'lucide-react';

interface Props {
  blobUrl: string;
  page?: number;
  highlightText?: string;
}

const PdfViewer: React.FC<Props> = ({ blobUrl, page = 1, highlightText }) => {
  if (!blobUrl) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
        <FileX size={32} className="text-slate-300" />
        <p className="text-sm text-slate-500">
          PDF 미리보기를 사용할 수 없습니다.
        </p>
        <p className="text-xs text-slate-400">
          새로고침 후에는 PDF 파일을 다시 업로드해주세요.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <iframe
        title="PDF 미리보기"
        src={`${blobUrl}#page=${page}`}
        className="flex-1 w-full"
      />
      {highlightText && (
        <div className="border-t border-slate-200 bg-amber-50 p-3">
          <div className="flex items-start gap-2">
            <Quote size={14} className="mt-0.5 shrink-0 text-amber-500" />
            <div>
              <p className="text-[11px] font-medium text-amber-700">참조 텍스트 (p.{page})</p>
              <p className="mt-1 text-xs text-amber-900 leading-relaxed">{highlightText}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PdfViewer;
