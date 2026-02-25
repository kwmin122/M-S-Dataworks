import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import { FileX, Download, Copy, Check, FileSpreadsheet, FileText, Presentation, Quote, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { getFileTextPreview, type TextPreviewPage } from '../../../services/kiraApiService';
import type { DocFileType } from '../../../types';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

interface Props {
  url: string;
  fileName: string;
  fileType: DocFileType;
  page?: number;
  highlightText?: string;
}

const FILE_TYPE_ICONS: Record<DocFileType, React.FC<{ size?: number; className?: string }>> = {
  pdf: FileText,
  excel: FileSpreadsheet,
  hwp: FileText,
  docx: FileText,
  ppt: Presentation,
  other: FileText,
};

const FILE_TYPE_LABELS: Record<DocFileType, string> = {
  pdf: 'PDF 문서',
  excel: 'Excel 스프레드시트',
  hwp: 'HWP 한글 문서',
  docx: 'Word 문서',
  ppt: 'PowerPoint 프레젠테이션',
  other: '문서',
};

const ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

// ── PDF Viewer with zoom controls ──

const PdfViewer: React.FC<{ url: string; page: number; highlightText?: string }> = ({
  url,
  page,
  highlightText,
}) => {
  const [numPages, setNumPages] = useState<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [zoom, setZoom] = useState(1.0);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (page <= 0 || !numPages) return;
    const el = pageRefs.current.get(page);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [page, numPages]);

  const onDocumentLoadSuccess = useCallback(({ numPages: total }: { numPages: number }) => {
    setNumPages(total);
  }, []);

  const highlightKeywords = useMemo(() => {
    if (!highlightText) return [];
    return highlightText
      .replace(/[.,;:!?()[\]{}'"·…~\-–—]/g, ' ')
      .split(/\s+/)
      .filter((w) => w.length >= 2)
      .slice(0, 12);
  }, [highlightText]);

  const customTextRenderer = useCallback(
    ({ str }: { str: string }) => {
      if (highlightKeywords.length === 0) return str;
      const lower = str.toLowerCase();
      let result = str;
      for (const kw of highlightKeywords) {
        const idx = lower.indexOf(kw.toLowerCase());
        if (idx !== -1) {
          const before = result.slice(0, idx);
          const match = result.slice(idx, idx + kw.length);
          const after = result.slice(idx + kw.length);
          result = `${before}<mark style="background-color:#fde68a;border-radius:2px;padding:1px 2px;">${match}</mark>${after}`;
          break;
        }
      }
      return result;
    },
    [highlightKeywords],
  );

  const setPageRef = useCallback((pageNum: number, el: HTMLDivElement | null) => {
    if (el) pageRefs.current.set(pageNum, el);
    else pageRefs.current.delete(pageNum);
  }, []);

  const handleZoomIn = () => {
    const nextIdx = ZOOM_STEPS.findIndex(z => z > zoom);
    if (nextIdx !== -1) setZoom(ZOOM_STEPS[nextIdx]);
  };
  const handleZoomOut = () => {
    const prevSteps = ZOOM_STEPS.filter(z => z < zoom);
    if (prevSteps.length > 0) setZoom(prevSteps[prevSteps.length - 1]);
  };
  const handleZoomReset = () => setZoom(1.0);

  const pageWidth = containerWidth > 0 ? containerWidth * zoom : undefined;

  return (
    <div className="flex h-full flex-col">
      {/* Highlight card */}
      {highlightText && (
        <div className="shrink-0 border-b border-slate-200 bg-amber-50 px-4 py-2.5">
          <div className="flex items-start gap-2">
            <Quote size={14} className="mt-0.5 shrink-0 text-amber-500" />
            <div>
              <p className="text-[11px] font-medium text-amber-700">참조 텍스트 (p.{page})</p>
              <p className="mt-0.5 text-xs text-amber-900 leading-relaxed line-clamp-2">{highlightText}</p>
            </div>
          </div>
        </div>
      )}

      {/* Zoom controls */}
      <div className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-1.5">
        <span className="text-xs text-slate-500">
          {numPages > 0 ? `${numPages}페이지` : '로딩 중...'}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleZoomOut}
            disabled={zoom <= ZOOM_STEPS[0]}
            className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-700 disabled:opacity-30"
            title="축소"
          >
            <ZoomOut size={15} />
          </button>
          <button
            type="button"
            onClick={handleZoomReset}
            className="min-w-[42px] rounded px-1.5 py-0.5 text-center text-xs font-medium text-slate-600 hover:bg-slate-200"
            title="원본 크기"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            type="button"
            onClick={handleZoomIn}
            disabled={zoom >= ZOOM_STEPS[ZOOM_STEPS.length - 1]}
            className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-700 disabled:opacity-30"
            title="확대"
          >
            <ZoomIn size={15} />
          </button>
          {zoom !== 1.0 && (
            <button
              type="button"
              onClick={handleZoomReset}
              className="ml-1 rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
              title="초기화"
            >
              <RotateCcw size={13} />
            </button>
          )}
        </div>
      </div>

      {/* PDF pages scroll */}
      <div ref={containerRef} className="flex-1 overflow-auto bg-slate-100">
        <Document
          file={url}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <div className="flex items-center justify-center p-12">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
            </div>
          }
          error={
            <div className="flex flex-col items-center justify-center gap-2 p-12 text-center">
              <FileX size={32} className="text-slate-300" />
              <p className="text-sm text-slate-500">PDF를 불러올 수 없습니다.</p>
            </div>
          }
        >
          {numPages > 0 && Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
            <div
              key={pageNum}
              ref={(el) => setPageRef(pageNum, el)}
              className="border-b border-slate-200 last:border-b-0"
            >
              <Page
                pageNumber={pageNum}
                width={pageWidth}
                renderTextLayer={true}
                renderAnnotationLayer={true}
                customTextRenderer={highlightText && pageNum === page ? customTextRenderer : undefined}
              />
            </div>
          ))}
        </Document>
      </div>
    </div>
  );
};

// ── HWP/DOCX Text Viewer ──

const TextFileViewer: React.FC<{ url: string; fileName: string; fileType: DocFileType }> = ({
  url,
  fileName,
  fileType,
}) => {
  const [pages, setPages] = useState<TextPreviewPage[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError('');

    // Extract relative path from full URL (remove API_BASE_URL prefix)
    const relPath = url.replace(/^https?:\/\/[^/]+/, '');

    getFileTextPreview(relPath)
      .then(res => {
        setPages(res.pages);
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : '텍스트를 추출할 수 없습니다.');
      })
      .finally(() => setLoading(false));
  }, [url]);

  const label = FILE_TYPE_LABELS[fileType] || '문서';

  const handleCopyAll = useCallback(async () => {
    if (!pages || pages.length === 0) return;
    const fullText = pages.map(p => p.text).join('\n\n');
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = fullText;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [pages]);

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
        <p className="text-sm text-slate-500">문서 텍스트를 추출하고 있어요...</p>
      </div>
    );
  }

  if (error || !pages || pages.length === 0) {
    // Fallback to download card
    const Icon = FILE_TYPE_ICONS[fileType] || FileText;
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
        <div className="rounded-2xl bg-slate-100 p-6">
          <Icon size={48} className="text-slate-400" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-700 break-all">{fileName}</p>
          <p className="mt-1 text-xs text-slate-500">{label}</p>
        </div>
        {error && <p className="text-xs text-red-400 max-w-[260px]">{error}</p>}
        <a
          href={url}
          download={fileName}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 transition-colors"
        >
          <Download size={16} />
          다운로드하여 확인
        </a>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header bar */}
      <div className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-1.5">
        <span className="text-xs text-slate-500">
          {label} · {pages.length}페이지
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => void handleCopyAll()}
            className="flex items-center gap-1 rounded px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-200 hover:text-slate-700 transition-colors"
            title="전체 텍스트 복사"
          >
            {copied ? <Check size={13} className="text-green-500" /> : <Copy size={13} />}
            {copied ? '복사됨' : '전체 복사'}
          </button>
          <a
            href={url}
            download={fileName}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-200 hover:text-slate-700"
          >
            <Download size={13} />
            원본
          </a>
        </div>
      </div>

      {/* Text content */}
      <div className="flex-1 overflow-auto bg-white px-5 py-4">
        {pages.map((p, i) => (
          <div key={i} className="mb-6 last:mb-0">
            {pages.length > 1 && (
              <div className="mb-2 flex items-center gap-2">
                <span className="text-[10px] font-medium text-slate-400 bg-slate-100 rounded px-1.5 py-0.5">
                  {p.page_number}페이지
                </span>
                <div className="flex-1 border-t border-slate-100" />
              </div>
            )}
            <div className="text-sm leading-relaxed text-slate-700 whitespace-pre-wrap break-words">
              {p.text || '(내용 없음)'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Main DocumentViewer ──

const DocumentViewer: React.FC<Props> = ({ url, fileName, fileType, page = 1, highlightText }) => {
  if (!url) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
        <FileX size={32} className="text-slate-300" />
        <p className="text-sm text-slate-500">문서 미리보기를 사용할 수 없습니다.</p>
      </div>
    );
  }

  // PDF → react-pdf viewer with zoom
  if (fileType === 'pdf') {
    return <PdfViewer url={url} page={page} highlightText={highlightText} />;
  }

  // HWP, DOCX → text extraction viewer
  if (fileType === 'hwp' || fileType === 'docx') {
    return <TextFileViewer url={url} fileName={fileName} fileType={fileType} />;
  }

  // Other formats → download card
  const Icon = FILE_TYPE_ICONS[fileType] || FileText;
  const label = FILE_TYPE_LABELS[fileType] || '문서';

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="rounded-2xl bg-slate-100 p-6">
        <Icon size={48} className="text-slate-400" />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-700 break-all">{fileName}</p>
        <p className="mt-1 text-xs text-slate-500">{label}</p>
      </div>
      <p className="text-xs text-slate-400 max-w-[240px]">
        이 파일 형식은 브라우저에서 직접 미리보기가 지원되지 않습니다.
      </p>
      <a
        href={url}
        download={fileName}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 transition-colors"
      >
        <Download size={16} />
        다운로드하여 확인
      </a>
    </div>
  );
};

export default DocumentViewer;
