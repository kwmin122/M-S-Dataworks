import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ChecklistStage from '../stages/ChecklistStage';
import type { PackageItem, PackageCompleteness } from '../../../services/studioApi';

vi.mock('../../../services/studioApi', async () => {
  const actual = await vi.importActual('../../../services/studioApi');
  return {
    ...actual,
    listPackageItems: vi.fn(),
    getPackageCompleteness: vi.fn(),
    updatePackageItemStatus: vi.fn(),
    attachEvidenceFile: vi.fn(),
  };
});

import {
  listPackageItems, getPackageCompleteness, updatePackageItemStatus, attachEvidenceFile,
} from '../../../services/studioApi';
const mockListItems = vi.mocked(listPackageItems);
const mockCompleteness = vi.mocked(getPackageCompleteness);
const mockUpdateStatus = vi.mocked(updatePackageItemStatus);
const mockAttachFile = vi.mocked(attachEvidenceFile);

const SAMPLE_ITEMS: PackageItem[] = [
  { id: 'i1', package_category: 'generated_document', document_code: 'proposal', document_label: '기술 제안서', required: true, status: 'generated', generation_target: 'proposal', sort_order: 1 },
  { id: 'i2', package_category: 'evidence', document_code: 'experience_cert', document_label: '용역수행실적확인서', required: true, status: 'missing', generation_target: null, sort_order: 10 },
  { id: 'i3', package_category: 'administrative', document_code: 'bid_letter', document_label: '입찰서', required: true, status: 'missing', generation_target: null, sort_order: 20 },
  { id: 'i4', package_category: 'price', document_code: 'price_proposal', document_label: '가격제안서', required: false, status: 'waived', generation_target: null, sort_order: 30 },
];

const SAMPLE_COMPLETENESS: PackageCompleteness = {
  total: 4,
  completed: 1,
  waived: 1,
  required_remaining: 2,
  completeness_pct: 50,
};

describe('ChecklistStage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListItems.mockResolvedValue(SAMPLE_ITEMS);
    mockCompleteness.mockResolvedValue(SAMPLE_COMPLETENESS);
  });

  it('renders checklist items with status badges', async () => {
    render(<ChecklistStage projectId="proj1" />);

    expect(await screen.findByText('기술 제안서')).toBeInTheDocument();
    expect(screen.getByText('용역수행실적확인서')).toBeInTheDocument();
    expect(screen.getByText('입찰서')).toBeInTheDocument();
    expect(screen.getByText('가격제안서')).toBeInTheDocument();

    // Status badges
    expect(screen.getByText('생성 완료')).toBeInTheDocument();
    expect(screen.getAllByText('미제출').length).toBe(2);
    // "면제" appears as both badge and button — at least one exists
    expect(screen.getAllByText('면제').length).toBeGreaterThanOrEqual(1);
  });

  it('renders completeness summary', async () => {
    render(<ChecklistStage projectId="proj1" />);

    await screen.findByText('50%');
    expect(screen.getByText('전체 4건')).toBeInTheDocument();
    expect(screen.getByText('완료 1건')).toBeInTheDocument();
    expect(screen.getByText('필수 미완료 2건')).toBeInTheDocument();
  });

  it('calls updatePackageItemStatus for generated → verified', async () => {
    mockUpdateStatus.mockResolvedValue({ id: 'i1', status: 'verified', document_code: 'proposal' });
    render(<ChecklistStage projectId="proj1" />);

    await screen.findByText('기술 제안서');

    // "확인" button should be next to generated item
    const verifyButtons = screen.getAllByText('확인');
    expect(verifyButtons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(verifyButtons[0]);

    await waitFor(() => {
      expect(mockUpdateStatus).toHaveBeenCalledWith('proj1', 'i1', 'verified');
    });
  });

  it('calls updatePackageItemStatus for missing → waived', async () => {
    mockUpdateStatus.mockResolvedValue({ id: 'i2', status: 'waived', document_code: 'experience_cert' });
    render(<ChecklistStage projectId="proj1" />);

    await screen.findByText('용역수행실적확인서');

    const waiveButtons = screen.getAllByText('면제');
    // Find the button (not the badge) — button has '면제' text but is a button element
    const waiveButton = waiveButtons.find(el => el.closest('button'));
    expect(waiveButton).toBeDefined();
    fireEvent.click(waiveButton!);

    await waitFor(() => {
      expect(mockUpdateStatus).toHaveBeenCalledWith('proj1', expect.any(String), 'waived');
    });
  });

  it('does not show evidence upload panel on generated_document items', async () => {
    render(<ChecklistStage projectId="proj1" />);

    await screen.findByText('기술 제안서');

    // generated_document should NOT have file input
    const fileInputs = document.querySelectorAll('input[type="file"]');
    // Only evidence + administrative items (i2, i3) should have file inputs, not i1 (generated_document)
    expect(fileInputs.length).toBe(2); // experience_cert + bid_letter
  });

  it('shows file input for evidence items with missing status', async () => {
    render(<ChecklistStage projectId="proj1" />);

    await screen.findByText('용역수행실적확인서');

    // Evidence items in missing status should have "파일 선택" label
    const fileLabels = screen.getAllByText('파일 선택');
    expect(fileLabels.length).toBe(2); // experience_cert + bid_letter
  });

  it('calls attachEvidenceFile with FormData on file upload', async () => {
    mockAttachFile.mockResolvedValue({ asset_id: 'a1', status: 'uploaded', document_code: 'experience_cert' });
    render(<ChecklistStage projectId="proj1" />);

    await screen.findByText('용역수행실적확인서');

    // Select a file
    const fileInputs = document.querySelectorAll('input[type="file"]');
    const testFile = new File(['test content'], '실적확인서.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInputs[0], { target: { files: [testFile] } });

    // Click upload
    const uploadButton = await screen.findByText('업로드');
    fireEvent.click(uploadButton);

    await waitFor(() => {
      expect(mockAttachFile).toHaveBeenCalledWith('proj1', 'i2', testFile);
    });
  });

  it('shows error state', async () => {
    mockListItems.mockRejectedValue(new Error('서버 오류'));
    mockCompleteness.mockRejectedValue(new Error('서버 오류'));
    render(<ChecklistStage projectId="proj1" />);

    expect(await screen.findByText('서버 오류')).toBeInTheDocument();
  });
});
