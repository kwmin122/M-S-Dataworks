import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import GenerateStage from '../stages/GenerateStage';
import type { StudioProject, GenerateResult } from '../../../services/studioApi';

vi.mock('../../../services/studioApi', async () => {
  const actual = await vi.importActual('../../../services/studioApi');
  return {
    ...actual,
    generateProposal: vi.fn(),
    getCurrentRevision: vi.fn(),
    listPackageItems: vi.fn(),
  };
});

import { generateProposal, getCurrentRevision, listPackageItems } from '../../../services/studioApi';
const mockGenerate = vi.mocked(generateProposal);
const mockGetRevision = vi.mocked(getCurrentRevision);
const mockListPackageItems = vi.mocked(listPackageItems);

const PROJECT_WITH_SNAPSHOT: StudioProject = {
  id: 'proj1',
  title: '테스트 프로젝트',
  status: 'ready_for_generation',
  project_type: 'studio',
  studio_stage: 'generate',
  pinned_style_skill_id: 'style-1',
  active_analysis_snapshot_id: 'snap-1',
  rfp_source_type: null,
  rfp_source_ref: null,
  settings_json: null,
  created_at: '2026-03-18T10:00:00Z',
  updated_at: '2026-03-18T10:00:00Z',
};

const PROJECT_NO_SNAPSHOT: StudioProject = {
  ...PROJECT_WITH_SNAPSHOT,
  active_analysis_snapshot_id: null,
  pinned_style_skill_id: null,
};

const SAMPLE_RESULT: GenerateResult = {
  run_id: 'run-abc123',
  revision_id: 'rev-def456',
  status: 'completed',
  generation_contract: {
    snapshot_id: 'snap-1',
    snapshot_version: 1,
    company_assets_count: 3,
    company_context_length: 200,
    pinned_style_skill_id: 'style-1',
    pinned_style_name: '테스트 스타일',
    pinned_style_version: 1,
    doc_type: 'proposal',
    total_pages: 50,
  },
  sections_count: 5,
  generation_time_sec: 12.3,
};

const noop = () => {};

describe('GenerateStage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no existing revision, empty package items
    mockGetRevision.mockRejectedValue(new Error('not found'));
    mockListPackageItems.mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
  });

  it('renders generate conditions and button', async () => {
    await act(async () => {
      render(<GenerateStage projectId="proj1" project={PROJECT_WITH_SNAPSHOT} onProjectUpdate={noop} />);
    });

    expect(screen.getByText('문서 생성')).toBeInTheDocument();
    expect(screen.getByText('공고 분석 완료')).toBeInTheDocument();
    expect(screen.getByText('스타일 핀')).toBeInTheDocument();
    expect(screen.getByText('제안서 생성')).toBeInTheDocument();
  });

  it('disables generate button without snapshot', async () => {
    await act(async () => {
      render(<GenerateStage projectId="proj1" project={PROJECT_NO_SNAPSHOT} onProjectUpdate={noop} />);
    });

    const button = screen.getByText('제안서 생성').closest('button');
    expect(button).toBeDisabled();
  });

  it('shows contract view on toggle', async () => {
    await act(async () => {
      render(<GenerateStage projectId="proj1" project={PROJECT_WITH_SNAPSHOT} onProjectUpdate={noop} />);
    });

    fireEvent.click(screen.getByText('입력 계약 보기'));
    expect(screen.getByText('생성 입력 계약 (예상)')).toBeInTheDocument();
    expect(screen.getByText(/snap-1/)).toBeInTheDocument();
  });

  it('calls generateProposal and shows result with preview', async () => {
    mockGenerate.mockResolvedValue(SAMPLE_RESULT);
    // After generation, getCurrentRevision returns content
    mockGetRevision
      .mockRejectedValueOnce(new Error('not found')) // initial mount
      .mockResolvedValueOnce({
        revision_id: 'rev-1',
        revision_number: 1,
        source: 'ai_generated',
        status: 'draft',
        title: '테스트 제안서',
        sections: [{ name: '개요', text: '테스트 개요 본문' }],
        quality_report: null,
        created_at: '2026-03-19T10:00:00Z',
      });
    const onUpdate = vi.fn();

    await act(async () => {
      render(<GenerateStage projectId="proj1" project={PROJECT_WITH_SNAPSHOT} onProjectUpdate={onUpdate} />);
    });

    await act(async () => {
      fireEvent.click(screen.getByText('제안서 생성'));
    });

    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledWith('proj1', { doc_type: 'proposal' });
    });

    expect(await screen.findByText('생성 완료')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument(); // sections_count
    expect(onUpdate).toHaveBeenCalled();

    // Preview should auto-show with section content
    expect(await screen.findByText('개요')).toBeInTheDocument();
    expect(screen.getByText('테스트 개요 본문')).toBeInTheDocument();
  });

  it('shows error state on generation failure', async () => {
    mockGenerate.mockRejectedValue(new Error('생성 실패'));

    await act(async () => {
      render(<GenerateStage projectId="proj1" project={PROJECT_WITH_SNAPSHOT} onProjectUpdate={noop} />);
    });

    await act(async () => {
      fireEvent.click(screen.getByText('제안서 생성'));
    });

    expect(await screen.findByText('생성 실패')).toBeInTheDocument();
  });

  it('shows actual generation contract fields after successful generation', async () => {
    mockGenerate.mockResolvedValue(SAMPLE_RESULT);

    await act(async () => {
      render(<GenerateStage projectId="proj1" project={PROJECT_WITH_SNAPSHOT} onProjectUpdate={noop} />);
    });

    await act(async () => {
      fireEvent.click(screen.getByText('제안서 생성'));
    });

    // Wait for result — contract auto-shows after generation
    await screen.findByText('생성 완료');

    // Actual contract heading
    expect(screen.getByText('생성 입력 계약 (실제 사용됨)')).toBeInTheDocument();

    // Contract fields from SAMPLE_RESULT.generation_contract
    expect(screen.getByText('snap-1')).toBeInTheDocument(); // snapshot_id
    expect(screen.getByText('v1')).toBeInTheDocument(); // snapshot_version
    expect(screen.getByText('3건')).toBeInTheDocument(); // company_assets_count
    expect(screen.getByText('200자')).toBeInTheDocument(); // company_context_length
    expect(screen.getByText('테스트 스타일 (v1)')).toBeInTheDocument(); // pinned_style_name + version
    expect(screen.getByText('proposal')).toBeInTheDocument(); // doc_type
    expect(screen.getByText('50p')).toBeInTheDocument(); // total_pages
  });

  it('shows pre-generation contract when toggled before generating', async () => {
    await act(async () => {
      render(<GenerateStage projectId="proj1" project={PROJECT_WITH_SNAPSHOT} onProjectUpdate={noop} />);
    });

    fireEvent.click(screen.getByText('입력 계약 보기'));

    // Pre-generation heading
    expect(screen.getByText('생성 입력 계약 (예상)')).toBeInTheDocument();
    // Contract shows snapshot, style, doc type items
    expect(screen.getByText('공고 분석 스냅샷')).toBeInTheDocument();
    expect(screen.getByText('핀 설정 스타일')).toBeInTheDocument();
  });
});
