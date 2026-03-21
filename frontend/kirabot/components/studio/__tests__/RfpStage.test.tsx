import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import RfpStage from '../stages/RfpStage';
import type { StudioProject, NaraSearchResult } from '../../../services/studioApi';

vi.mock('../../../services/studioApi', async () => {
  const actual = await vi.importActual('../../../services/studioApi');
  return {
    ...actual,
    searchNaraBids: vi.fn(),
    uploadAndAnalyzeRfp: vi.fn(),
  };
});

import { searchNaraBids, uploadAndAnalyzeRfp } from '../../../services/studioApi';
const mockSearchNaraBids = vi.mocked(searchNaraBids);
const mockUploadAndAnalyzeRfp = vi.mocked(uploadAndAnalyzeRfp);

const PROJECT: StudioProject = {
  id: 'proj1',
  title: '테스트 프로젝트',
  status: 'draft',
  project_type: 'studio',
  studio_stage: 'rfp',
  pinned_style_skill_id: null,
  active_analysis_snapshot_id: null,
  rfp_source_type: null,
  rfp_source_ref: null,
  created_at: '2026-03-18T10:00:00Z',
  updated_at: '2026-03-18T10:00:00Z',
};

const PROJECT_WITH_SNAPSHOT: StudioProject = {
  ...PROJECT,
  active_analysis_snapshot_id: 'snap-1',
};

const SEARCH_RESULT: NaraSearchResult = {
  notices: [
    {
      id: 'bid-1',
      title: '정보시스템 구축 사업',
      issuingOrg: '국토교통부',
      region: '서울',
      deadlineAt: '2026-04-01T18:00:00Z',
      estimatedPrice: '5억원',
      category: '용역',
      awardMethod: '협상에 의한 계약',
      url: 'https://nara.go.kr/bid/1',
    },
  ],
  total: 1,
  page: 1,
  pageSize: 10,
};

describe('RfpStage', () => {
  const mockOnAnalyze = vi.fn();
  const mockOnClassify = vi.fn();
  const mockOnProjectUpdate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnAnalyze.mockResolvedValue(undefined);
    mockOnClassify.mockResolvedValue(undefined);
  });

  it('renders search button (not "준비 중")', () => {
    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    expect(screen.getByText('나라장터 검색')).toBeInTheDocument();
    expect(screen.queryByText('준비 중')).not.toBeInTheDocument();
  });

  it('renders upload button (not "준비 중")', () => {
    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    expect(screen.getByText('파일 업로드')).toBeInTheDocument();
  });

  it('search panel opens on click', () => {
    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    // Panel not visible initially
    expect(screen.queryByText('나라장터 공고 검색')).not.toBeInTheDocument();

    // Click search button
    fireEvent.click(screen.getByText('나라장터 검색'));

    // Panel visible
    expect(screen.getByText('나라장터 공고 검색')).toBeInTheDocument();
  });

  it('search calls searchNaraBids API', async () => {
    mockSearchNaraBids.mockResolvedValue(SEARCH_RESULT);

    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    // Open search panel
    fireEvent.click(screen.getByText('나라장터 검색'));

    // Type keyword
    const input = screen.getByPlaceholderText('검색어 입력 (예: 정보시스템, 홈페이지 구축)');
    fireEvent.change(input, { target: { value: '정보시스템' } });

    // Click search button
    fireEvent.click(screen.getByText('검색'));

    await waitFor(() => {
      expect(mockSearchNaraBids).toHaveBeenCalledWith({
        keywords: '정보시스템',
        category: 'all',
        page: 1,
      });
    });

    // Result should display
    expect(await screen.findByText('정보시스템 구축 사업')).toBeInTheDocument();
  });

  it('selecting a bid fills the textarea', async () => {
    mockSearchNaraBids.mockResolvedValue(SEARCH_RESULT);

    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    // Open search, search, select
    fireEvent.click(screen.getByText('나라장터 검색'));
    const input = screen.getByPlaceholderText('검색어 입력 (예: 정보시스템, 홈페이지 구축)');
    fireEvent.change(input, { target: { value: '정보시스템' } });
    fireEvent.click(screen.getByText('검색'));

    await screen.findByText('정보시스템 구축 사업');

    // Click "선택" button
    fireEvent.click(screen.getByText('선택'));

    // Textarea should have the bid info
    const textarea = screen.getByPlaceholderText('공고문 전문 또는 주요 내용을 붙여넣기 해주세요. (최소 50자)') as HTMLTextAreaElement;
    expect(textarea.value).toContain('[공고명] 정보시스템 구축 사업');
    expect(textarea.value).toContain('[발주기관] 국토교통부');
  });

  it('file upload triggers uploadAndAnalyzeRfp', async () => {
    mockUploadAndAnalyzeRfp.mockResolvedValue({
      snapshot_id: 'snap-new',
      summary_md: '분석 완료',
      filename: 'rfp.pdf',
    } as any);

    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    const file = new File(['dummy content'], 'rfp.pdf', { type: 'application/pdf' });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockUploadAndAnalyzeRfp).toHaveBeenCalledWith('proj1', file);
    });
  });

  it('file validation: rejects oversized file (>20MB)', async () => {
    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    // Create a file > 20MB
    const largeFile = new File(['x'], 'big.pdf', { type: 'application/pdf' });
    Object.defineProperty(largeFile, 'size', { value: 21 * 1024 * 1024 });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [largeFile] } });

    // Error should display
    expect(await screen.findByText(/파일 크기가 너무 큽니다/)).toBeInTheDocument();
    expect(mockUploadAndAnalyzeRfp).not.toHaveBeenCalled();
  });

  it('file validation: rejects invalid extension', async () => {
    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    const badFile = new File(['content'], 'malware.exe', { type: 'application/octet-stream' });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [badFile] } });

    expect(await screen.findByText(/지원하지 않는 파일 형식입니다/)).toBeInTheDocument();
    expect(mockUploadAndAnalyzeRfp).not.toHaveBeenCalled();
  });

  it('text analysis: disabled when < 50 chars, enabled when >= 50', () => {
    render(
      <RfpStage
        project={PROJECT}
        onAnalyze={mockOnAnalyze}
        onClassify={mockOnClassify}
        onProjectUpdate={mockOnProjectUpdate}
      />,
    );

    const textarea = screen.getByPlaceholderText('공고문 전문 또는 주요 내용을 붙여넣기 해주세요. (최소 50자)');
    const analyzeButton = screen.getByRole('button', { name: '공고 분석' });

    // Initially disabled (empty text)
    expect(analyzeButton).toBeDisabled();

    // Short text — still disabled
    fireEvent.change(textarea, { target: { value: '짧은 텍스트' } });
    expect(analyzeButton).toBeDisabled();

    // 50+ chars — enabled
    const longText = '가'.repeat(50);
    fireEvent.change(textarea, { target: { value: longText } });
    expect(analyzeButton).not.toBeDisabled();
  });
});
