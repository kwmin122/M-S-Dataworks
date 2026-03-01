import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import { FileX, Download, Copy, Check, FileSpreadsheet, FileText, Presentation, Quote, ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from 'lucide-react';
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

const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// ── PDF Viewer: single-page mode with zoom + navigation ──

const PdfViewer: React.FC<{ url: string; page: number; highlightText?: string }> = ({
  url,
  page,
  highlightText,
}) => {
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(page || 1);
  const [zoom, setZoom] = useState(1.0);
  const [containerWidth, setContainerWidth] = useState(0);
  const [isEditingPage, setIsEditingPage] = useState(false);
  const [pageInput, setPageInput] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const pageInputRef = useRef<HTMLInputElement>(null);

  // Track container width for fit-to-width rendering
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) setContainerWidth(entry.contentRect.width);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Auto-navigate when page prop changes (reference click)
  useEffect(() => {
    if (page > 0 && numPages > 0) {
      setCurrentPage(Math.min(page, numPages));
    }
  }, [page, numPages]);

  // Reset scroll position when page or zoom changes
  useEffect(() => {
    if (wrapperRef.current) wrapperRef.current.scrollTo(0, 0);
  }, [currentPage, zoom]);

  const onDocumentLoadSuccess = useCallback(({ numPages: total }: { numPages: number }) => {
    setNumPages(total);
    if (page > 0 && page <= total) setCurrentPage(page);
  }, [page]);

  // Highlight keywords for yellow marks
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
      if (highlightKeywords.length === 0) return escapeHtml(str);
      const lower = str.toLowerCase();
      for (const kw of highlightKeywords) {
        const idx = lower.indexOf(kw.toLowerCase());
        if (idx !== -1) {
          const before = escapeHtml(str.slice(0, idx));
          const match = escapeHtml(str.slice(idx, idx + kw.length));
          const after = escapeHtml(str.slice(idx + kw.length));
          return `${before}<mark style="background-color:#fde68a;border-radius:2px;padding:1px 2px;">${match}</mark>${after}`;
        }
      }
      return escapeHtml(str);
    },
    [highlightKeywords],
  );

  // Page navigation
  const goToPage = useCallback((p: number) => {
    if (p >= 1 && p <= numPages) setCurrentPage(p);
  }, [numPages]);
  const goPrev = useCallback(() => goToPage(currentPage - 1), [currentPage, goToPage]);
  const goNext = useCallback(() => goToPage(currentPage + 1), [currentPage, goToPage]);

  // Zoom controls
  const handleZoomIn = useCallback(() => {
    const nextIdx = ZOOM_STEPS.findIndex(z => z > zoom);
    if (nextIdx !== -1) setZoom(ZOOM_STEPS[nextIdx]);
  }, [zoom]);
  const handleZoomOut = useCallback(() => {
    const prevSteps = ZOOM_STEPS.filter(z => z < zoom);
    if (prevSteps.length > 0) setZoom(prevSteps[prevSteps.length - 1]);
  }, [zoom]);
  const handleZoomReset = useCallback(() => setZoom(1.0), []);

  // Page number input
  const startEditingPage = useCallback(() => {
    setPageInput(String(currentPage));
    setIsEditingPage(true);
    setTimeout(() => pageInputRef.current?.select(), 0);
  }, [currentPage]);

  const commitPageInput = useCallback(() => {
    const p = parseInt(pageInput, 10);
    if (!isNaN(p) && p >= 1 && p <= numPages) setCurrentPage(p);
    setIsEditingPage(false);
  }, [pageInput, numPages]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (isEditingPage) return;
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;

      switch (e.key) {
        case 'ArrowLeft': case 'ArrowUp': e.preventDefault(); goPrev(); break;
        case 'ArrowRight': case 'ArrowDown': e.preventDefault(); goNext(); break;
        case '+': case '=': e.preventDefault(); handleZoomIn(); break;
        case '-': e.preventDefault(); handleZoomOut(); break;
        case '0': e.preventDefault(); handleZoomReset(); break;
        case 'Home': e.preventDefault(); goToPage(1); break;
        case 'End': e.preventDefault(); goToPage(numPages); break;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isEditingPage, goPrev, goNext, handleZoomIn, handleZoomOut, handleZoomReset, goToPage, numPages]);

  const pageWidth = containerWidth > 0 ? containerWidth : undefined;

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

      {/* Toolbar: navigation + zoom + download */}
      <div className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-slate-50 px-2 py-1">
        {/* Page navigation */}
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={goPrev}
            disabled={currentPage <= 1}
            className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-700 disabled:opacity-30"
            title="이전 페이지 (←)"
            aria-label="이전 페이지"
          >
            <ChevronLeft size={16} />
          </button>
          {isEditingPage ? (
            <input
              ref={pageInputRef}
              type="text"
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value.replace(/\D/g, ''))}
              onBlur={commitPageInput}
              onKeyDown={(e) => { if (e.key === 'Enter') commitPageInput(); if (e.key === 'Escape') setIsEditingPage(false); }}
              className="w-10 rounded border border-slate-300 bg-white px-1 py-0.5 text-center text-xs text-slate-700 outline-none focus:border-primary-400"
              autoFocus
            />
          ) : (
            <button
              type="button"
              onClick={startEditingPage}
              className="rounded px-1.5 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-200 tabular-nums"
              title="페이지로 이동 (클릭)"
            >
              {numPages > 0 ? `${currentPage} / ${numPages}` : '...'}
            </button>
          )}
          <button
            type="button"
            onClick={goNext}
            disabled={currentPage >= numPages}
            className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-700 disabled:opacity-30"
            title="다음 페이지 (→)"
            aria-label="다음 페이지"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={handleZoomOut}
            disabled={zoom <= ZOOM_STEPS[0]}
            className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-700 disabled:opacity-30"
            title="축소 (−)"
            aria-label="축소"
          >
            <ZoomOut size={15} />
          </button>
          <button
            type="button"
            onClick={handleZoomReset}
            className="min-w-[40px] rounded px-1 py-0.5 text-center text-xs font-medium text-slate-600 hover:bg-slate-200 tabular-nums"
            title="원본 크기"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            type="button"
            onClick={handleZoomIn}
            disabled={zoom >= ZOOM_STEPS[ZOOM_STEPS.length - 1]}
            className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-700 disabled:opacity-30"
            title="확대 (+)"
            aria-label="확대"
          >
            <ZoomIn size={15} />
          </button>
          <a
            href={url}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="ml-1 rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
            title="다운로드"
          >
            <Download size={14} />
          </a>
        </div>
      </div>

      {/* Single-page PDF render with zoom */}
      <div ref={containerRef} className="relative flex-1 overflow-hidden bg-slate-100">
        <div
          ref={wrapperRef}
          className="absolute inset-0 overflow-auto"
        >
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
            {numPages > 0 && (
              <Page
                pageNumber={currentPage}
                width={pageWidth}
                scale={zoom}
                renderTextLayer={true}
                renderAnnotationLayer={true}
                customTextRenderer={highlightText && currentPage === page ? customTextRenderer : undefined}
              />
            )}
          </Document>
        </div>
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
