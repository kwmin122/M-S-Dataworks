import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CompanyStage from '../stages/CompanyStage';
import type { MergedCompanyData, CompanyAsset } from '../../../services/studioApi';

// Mock the studioApi module
vi.mock('../../../services/studioApi', async () => {
  const actual = await vi.importActual('../../../services/studioApi');
  return {
    ...actual,
    getCompanyMerged: vi.fn(),
    listCompanyAssets: vi.fn(),
    addCompanyAsset: vi.fn(),
    promoteCompanyAsset: vi.fn(),
  };
});

import { getCompanyMerged, listCompanyAssets, addCompanyAsset, promoteCompanyAsset } from '../../../services/studioApi';
const mockGetMerged = vi.mocked(getCompanyMerged);
const mockListAssets = vi.mocked(listCompanyAssets);
const mockAddAsset = vi.mocked(addCompanyAsset);
const mockPromote = vi.mocked(promoteCompanyAsset);

const SAMPLE_MERGED: MergedCompanyData = {
  profile: { id: 'p1', company_name: '테스트 주식회사', business_type: 'IT', headcount: 50, source: 'shared' },
  track_records: [
    { id: 'tr1', project_name: '공유 실적', client_name: '국토부', source: 'shared' },
    { id: 'tr2', project_name: '스테이징 실적', client_name: '과기부', source: 'staging', asset_category: 'track_record', label: '스테이징 실적' },
  ],
  personnel: [
    { id: 'pe1', name: '홍길동', role: 'PM', source: 'shared' },
  ],
  other_assets: [
    { id: 'tech1', name: 'React', source: 'staging', asset_category: 'technology', label: 'React' },
  ],
};

const SAMPLE_STAGING: CompanyAsset[] = [
  {
    id: 'tr2',
    asset_category: 'track_record',
    label: '스테이징 실적',
    content_json: { project_name: '스테이징 실적' },
    promoted_at: null,
    promoted_to_id: null,
    created_at: '2026-03-18T10:00:00Z',
  },
  {
    id: 'tech1',
    asset_category: 'technology',
    label: 'React',
    content_json: { name: 'React' },
    promoted_at: null,
    promoted_to_id: null,
    created_at: '2026-03-18T10:00:00Z',
  },
];

describe('CompanyStage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset window.confirm
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('renders merged view with shared and staging items', async () => {
    mockGetMerged.mockResolvedValue(SAMPLE_MERGED);
    mockListAssets.mockResolvedValue(SAMPLE_STAGING);

    render(<CompanyStage projectId="test-proj" />);

    // Wait for data to load — profile is expanded by default
    expect(await screen.findByText('테스트 주식회사')).toBeInTheDocument();

    // Profile section header
    expect(screen.getByText('회사 기본정보')).toBeInTheDocument();

    // Expand track_record section to see items
    const trackRecordHeader = screen.getByText('실적');
    fireEvent.click(trackRecordHeader);
    expect(screen.getByText('공유 실적')).toBeInTheDocument();
    expect(screen.getByText('스테이징 실적')).toBeInTheDocument();
  });

  it('shows staging and shared badges', async () => {
    mockGetMerged.mockResolvedValue(SAMPLE_MERGED);
    mockListAssets.mockResolvedValue(SAMPLE_STAGING);

    render(<CompanyStage projectId="test-proj" />);
    // Profile section expanded by default, expand track_record
    await screen.findByText('테스트 주식회사');
    fireEvent.click(screen.getByText('실적'));

    // Both source badges should be visible
    const sharedBadges = screen.getAllByText('공유');
    expect(sharedBadges.length).toBeGreaterThanOrEqual(1);

    const stagingBadges = screen.getAllByText('스테이징');
    expect(stagingBadges.length).toBeGreaterThanOrEqual(1);
  });

  it('calls promoteCompanyAsset on promote button click', async () => {
    mockGetMerged.mockResolvedValue(SAMPLE_MERGED);
    mockListAssets.mockResolvedValue(SAMPLE_STAGING);
    mockPromote.mockResolvedValue({ promoted: true, promoted_to_id: 'new-shared-id' });
    // After promote, reload returns updated data
    mockGetMerged.mockResolvedValueOnce(SAMPLE_MERGED).mockResolvedValueOnce({
      ...SAMPLE_MERGED,
      track_records: SAMPLE_MERGED.track_records.map(t =>
        t.id === 'tr2' ? { ...t, source: 'shared' as const } : t
      ),
    });
    mockListAssets.mockResolvedValueOnce(SAMPLE_STAGING).mockResolvedValueOnce([
      { ...SAMPLE_STAGING[0], promoted_at: '2026-03-18T12:00:00Z', promoted_to_id: 'new-shared-id' },
      SAMPLE_STAGING[1],
    ]);

    render(<CompanyStage projectId="test-proj" />);
    // Expand track_record section (profile is default expanded)
    await screen.findByText('실적');
    fireEvent.click(screen.getByText('실적'));
    await screen.findByText('스테이징 실적');

    // Find and click promote button
    const promoteButtons = screen.getAllByText('승격');
    expect(promoteButtons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(promoteButtons[0]);

    await waitFor(() => {
      expect(mockPromote).toHaveBeenCalledWith('test-proj', 'tr2');
    });
  });

  it('shows loading and error states', async () => {
    mockGetMerged.mockRejectedValue(new Error('서버 오류'));
    mockListAssets.mockRejectedValue(new Error('서버 오류'));

    render(<CompanyStage projectId="test-proj" />);

    // Should show error
    expect(await screen.findByText('서버 오류')).toBeInTheDocument();
    expect(screen.getByText('다시 시도')).toBeInTheDocument();
  });

  it('shows profile add form when no profile exists and calls addCompanyAsset', async () => {
    // Empty org — no profile
    const emptyMerged: MergedCompanyData = {
      profile: null,
      track_records: [],
      personnel: [],
      other_assets: [],
    };
    mockGetMerged.mockResolvedValue(emptyMerged);
    mockListAssets.mockResolvedValue([]);
    mockAddAsset.mockResolvedValue({
      id: 'new-profile',
      asset_category: 'profile',
      label: '테스트 회사',
      content_json: { company_name: '테스트 회사', headcount: 10 },
      promoted_at: null,
      promoted_to_id: null,
      created_at: '2026-03-18T10:00:00Z',
    });
    // After save, reload with new profile
    mockGetMerged.mockResolvedValueOnce(emptyMerged).mockResolvedValueOnce({
      ...emptyMerged,
      profile: { id: 'new-profile', company_name: '테스트 회사', headcount: 10, source: 'staging' },
    });
    mockListAssets.mockResolvedValueOnce([]).mockResolvedValueOnce([{
      id: 'new-profile',
      asset_category: 'profile' as const,
      label: '테스트 회사',
      content_json: { company_name: '테스트 회사', headcount: 10 },
      promoted_at: null,
      promoted_to_id: null,
      created_at: '2026-03-18T10:00:00Z',
    }]);

    render(<CompanyStage projectId="test-proj" />);

    // Wait for load — profile section is expanded by default (even without data)
    // Click add button (no need to expand — profile is default expanded)
    const addButton = await screen.findByText('회사 기본정보 추가');
    fireEvent.click(addButton);

    // Fill in the form
    const companyNameInput = screen.getByLabelText('회사명');
    fireEvent.change(companyNameInput, { target: { value: '테스트 회사' } });

    const headcountInput = screen.getByLabelText('직원 수');
    fireEvent.change(headcountInput, { target: { value: '10' } });

    // Submit
    const saveButton = screen.getByText('저장');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockAddAsset).toHaveBeenCalledWith('test-proj', {
        asset_category: 'profile',
        label: '테스트 회사',
        content_json: { company_name: '테스트 회사', headcount: 10 },
      });
    });
  });

  it('shows add form for track_record and calls addCompanyAsset', async () => {
    const emptyMerged: MergedCompanyData = {
      profile: null,
      track_records: [],
      personnel: [],
      other_assets: [],
    };
    mockGetMerged.mockResolvedValue(emptyMerged);
    mockListAssets.mockResolvedValue([]);
    mockAddAsset.mockResolvedValue({
      id: 'new-tr',
      asset_category: 'track_record',
      label: '테스트 실적',
      content_json: { project_name: '테스트 실적', client_name: '교육부' },
      promoted_at: null,
      promoted_to_id: null,
      created_at: '2026-03-18T10:00:00Z',
    });

    render(<CompanyStage projectId="test-proj" />);

    // Expand track_record section (profile is default expanded)
    await screen.findByText('실적');
    fireEvent.click(screen.getByText('실적'));
    const addButton = await screen.findByText('실적 추가');
    fireEvent.click(addButton);

    const nameInput = screen.getByLabelText('프로젝트명');
    fireEvent.change(nameInput, { target: { value: '테스트 실적' } });

    const clientInput = screen.getByLabelText('발주처');
    fireEvent.change(clientInput, { target: { value: '교육부' } });

    fireEvent.click(screen.getByText('저장'));

    await waitFor(() => {
      expect(mockAddAsset).toHaveBeenCalledWith('test-proj', {
        asset_category: 'track_record',
        label: '테스트 실적',
        content_json: { project_name: '테스트 실적', client_name: '교육부' },
      });
    });
  });
});
