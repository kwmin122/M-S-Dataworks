import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ReviewStage from '../stages/ReviewStage';
import type { StudioProject, CurrentRevisionData, ProposalDiffResult, RelearnResult } from '../../../services/studioApi';

vi.mock('../../../services/studioApi', async () => {
  const actual = await vi.importActual('../../../services/studioApi');
  return {
    ...actual,
    getCurrentRevision: vi.fn(),
    saveEditedDocument: vi.fn(),
    getDocumentDiff: vi.fn(),
    relearnDocumentStyle: vi.fn(),
    pinStyleSkill: vi.fn(),
    generateProposal: vi.fn(),
    // backward-compat aliases still exist in the module, no need to mock separately
  };
});

import {
  getCurrentRevision, saveEditedDocument, getDocumentDiff,
  relearnDocumentStyle, pinStyleSkill, generateProposal,
} from '../../../services/studioApi';

const mockGetRevision = vi.mocked(getCurrentRevision);
const mockSaveEdited = vi.mocked(saveEditedDocument);
const mockGetDiff = vi.mocked(getDocumentDiff);
const mockRelearn = vi.mocked(relearnDocumentStyle);
const mockPin = vi.mocked(pinStyleSkill);
const mockGenerate = vi.mocked(generateProposal);

const PROJECT: StudioProject = {
  id: 'proj1', title: '테스트', status: 'draft', project_type: 'studio',
  studio_stage: 'review', pinned_style_skill_id: 'sk1',
  active_analysis_snapshot_id: 'snap1',
  rfp_source_type: null, rfp_source_ref: null, settings_json: null,
  created_at: '2026-03-19T10:00:00Z', updated_at: '2026-03-19T10:00:00Z',
};

const REVISION: CurrentRevisionData = {
  revision_id: 'rev1', revision_number: 1, doc_type: 'proposal',
  source: 'ai_generated', status: 'draft', title: '테스트 제안서',
  sections: [
    { name: '개요', text: '원본 개요 텍스트' },
    { name: '본론', text: '원본 본론 텍스트' },
  ],
  quality_report: null, created_at: '2026-03-19T10:00:00Z',
};

const WBS_REVISION: CurrentRevisionData = {
  revision_id: 'rev-wbs1', revision_number: 1, doc_type: 'execution_plan',
  source: 'ai_generated', status: 'draft', title: '테스트 수행계획서',
  sections: [
    { name: '1단계', text: '분석 및 설계' },
    { name: '2단계', text: '개발 및 테스트' },
  ],
  quality_report: null, created_at: '2026-03-19T10:00:00Z',
};

const DIFF: ProposalDiffResult = {
  sections: [
    { name: '개요', original: '원본 개요 텍스트', edited: '수정된 개요', changed: true },
    { name: '본론', original: '원본 본론 텍스트', edited: '원본 본론 텍스트', changed: false },
  ],
  changed_sections_count: 1,
  total_sections: 2,
  edit_rate: 0.3,
};

const WBS_DIFF: ProposalDiffResult = {
  sections: [
    { name: '1단계', original: '분석 및 설계', edited: '분석·설계·PoC', changed: true },
    { name: '2단계', original: '개발 및 테스트', edited: '개발 및 테스트', changed: false },
  ],
  changed_sections_count: 1,
  total_sections: 2,
  edit_rate: 0.25,
};

const RELEARN: RelearnResult = {
  new_skill_id: 'sk-new', new_skill_version: 2,
  derived_from_id: 'sk1', edit_notes_count: 1,
};

const noop = () => {};

describe('ReviewStage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetRevision.mockResolvedValue(REVISION);
  });

  it('loads and renders current proposal revision for editing', async () => {
    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} />);

    expect(await screen.findByText('테스트 제안서 — 리비전 #1')).toBeInTheDocument();
    // Section edit areas
    expect(screen.getByDisplayValue('원본 개요 텍스트')).toBeInTheDocument();
    expect(screen.getByDisplayValue('원본 본론 텍스트')).toBeInTheDocument();
  });

  it('allows editing section text', async () => {
    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} />);

    await screen.findByDisplayValue('원본 개요 텍스트');
    const textarea = screen.getByDisplayValue('원본 개요 텍스트') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '수정된 개요' } });
    expect(textarea.value).toBe('수정된 개요');
  });

  it('saves edited proposal and shows diff', async () => {
    mockSaveEdited.mockResolvedValue({ revision_id: 'rev2', revision_number: 2, source: 'user_edited' });
    mockGetDiff.mockResolvedValue(DIFF);

    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} />);
    await screen.findByDisplayValue('원본 개요 텍스트');

    fireEvent.click(screen.getByText('수정 저장 및 비교'));

    await waitFor(() => {
      expect(mockSaveEdited).toHaveBeenCalledWith('proj1', 'proposal', expect.any(Array));
    });

    // Diff view should appear
    expect(await screen.findByText('변경 비교')).toBeInTheDocument();
    expect(screen.getByText('변경됨')).toBeInTheDocument();
  });

  it('renders diff view with before/after', async () => {
    mockSaveEdited.mockResolvedValue({ revision_id: 'rev2', revision_number: 2, source: 'user_edited' });
    mockGetDiff.mockResolvedValue(DIFF);

    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} />);
    await screen.findByDisplayValue('원본 개요 텍스트');

    fireEvent.click(screen.getByText('수정 저장 및 비교'));

    await screen.findByText('변경 비교');
    expect(screen.getByText('1/2 섹션 변경 · 편집률 30%')).toBeInTheDocument();
  });

  it('calls relearnDocumentStyle on relearn button click', async () => {
    mockSaveEdited.mockResolvedValue({ revision_id: 'rev2', revision_number: 2, source: 'user_edited' });
    mockGetDiff.mockResolvedValue(DIFF);
    mockRelearn.mockResolvedValue(RELEARN);

    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} />);
    await screen.findByDisplayValue('원본 개요 텍스트');

    fireEvent.click(screen.getByText('수정 저장 및 비교'));
    await screen.findByText('수정 패턴 학습');

    fireEvent.click(screen.getByText('수정 패턴 학습'));

    await waitFor(() => {
      expect(mockRelearn).toHaveBeenCalledWith('proj1', 'proposal');
    });

    // Relearn result
    expect(await screen.findByText('학습 완료')).toBeInTheDocument();
    expect(screen.getByText(/v2/)).toBeInTheDocument();
  });

  it('pins new style and triggers regenerate', async () => {
    mockSaveEdited.mockResolvedValue({ revision_id: 'rev2', revision_number: 2, source: 'user_edited' });
    mockGetDiff.mockResolvedValue(DIFF);
    mockRelearn.mockResolvedValue(RELEARN);
    mockPin.mockResolvedValue({ pinned_style_skill_id: 'sk-new' });
    mockGenerate.mockResolvedValue({
      run_id: 'run2', revision_id: 'rev3', status: 'completed',
      generation_contract: {
        snapshot_id: 'snap1', snapshot_version: 1, company_assets_count: 0,
        company_context_length: 0, pinned_style_skill_id: 'sk-new',
        pinned_style_name: '학습 v2', pinned_style_version: 2,
        doc_type: 'proposal', total_pages: 50,
      },
      sections_count: 2, generation_time_sec: 1.0,
    });
    // After regenerate, loadRevision returns updated data
    mockGetRevision
      .mockResolvedValueOnce(REVISION)  // initial load
      .mockResolvedValueOnce({ ...REVISION, revision_number: 3, sections: [{ name: '개요', text: '학습 반영 개요' }] });

    const onUpdate = vi.fn();
    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={onUpdate} />);

    // Edit → save → diff → relearn → pin+regenerate
    await screen.findByDisplayValue('원본 개요 텍스트');
    fireEvent.click(screen.getByText('수정 저장 및 비교'));
    await screen.findByText('수정 패턴 학습');
    fireEvent.click(screen.getByText('수정 패턴 학습'));
    await screen.findByText('새 스타일 적용 및 재생성');
    fireEvent.click(screen.getByText('새 스타일 적용 및 재생성'));

    await waitFor(() => {
      expect(mockPin).toHaveBeenCalledWith('proj1', 'sk-new');
      expect(mockGenerate).toHaveBeenCalledWith('proj1', { doc_type: 'proposal' });
      expect(onUpdate).toHaveBeenCalled();
    });
  });

  it('shows error when no revision exists', async () => {
    mockGetRevision.mockRejectedValue(new Error('not found'));
    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} />);

    expect(await screen.findByText(/먼저 제안서를 생성해주세요/)).toBeInTheDocument();
  });

  // --- Multi-Doc Relearn: WBS (execution_plan) ---

  it('loads execution_plan revision when docType="execution_plan"', async () => {
    mockGetRevision.mockResolvedValue(WBS_REVISION);
    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} docType="execution_plan" />);

    expect(await screen.findByText('테스트 수행계획서 — 리비전 #1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('분석 및 설계')).toBeInTheDocument();
    expect(screen.getByDisplayValue('개발 및 테스트')).toBeInTheDocument();
    // Check doc label in description
    expect(screen.getByText(/수행계획서를 수정하고/)).toBeInTheDocument();
  });

  it('calls doc-type-aware APIs for execution_plan save+diff+relearn', async () => {
    mockGetRevision.mockResolvedValue(WBS_REVISION);
    mockSaveEdited.mockResolvedValue({ revision_id: 'rev-wbs2', revision_number: 2, source: 'user_edited' });
    mockGetDiff.mockResolvedValue(WBS_DIFF);
    mockRelearn.mockResolvedValue(RELEARN);

    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} docType="execution_plan" />);
    await screen.findByDisplayValue('분석 및 설계');

    // Save
    fireEvent.click(screen.getByText('수정 저장 및 비교'));
    await waitFor(() => {
      expect(mockSaveEdited).toHaveBeenCalledWith('proj1', 'execution_plan', expect.any(Array));
    });

    // Diff loaded
    await screen.findByText('변경 비교');
    await waitFor(() => {
      expect(mockGetDiff).toHaveBeenCalledWith('proj1', 'execution_plan');
    });

    // Relearn
    fireEvent.click(screen.getByText('수정 패턴 학습'));
    await waitFor(() => {
      expect(mockRelearn).toHaveBeenCalledWith('proj1', 'execution_plan');
    });
  });

  it('regenerates with correct doc_type for execution_plan', async () => {
    mockGetRevision.mockResolvedValue(WBS_REVISION);
    mockSaveEdited.mockResolvedValue({ revision_id: 'rev-wbs2', revision_number: 2, source: 'user_edited' });
    mockGetDiff.mockResolvedValue(WBS_DIFF);
    mockRelearn.mockResolvedValue(RELEARN);
    mockPin.mockResolvedValue({ pinned_style_skill_id: 'sk-new' });
    mockGenerate.mockResolvedValue({
      run_id: 'run-wbs2', revision_id: 'rev-wbs3', status: 'completed',
      generation_contract: {
        snapshot_id: 'snap1', snapshot_version: 1, company_assets_count: 0,
        company_context_length: 0, pinned_style_skill_id: 'sk-new',
        pinned_style_name: '학습 v2', pinned_style_version: 2,
        doc_type: 'execution_plan', total_pages: 30,
      },
      sections_count: 2, generation_time_sec: 1.0,
    });
    mockGetRevision
      .mockResolvedValueOnce(WBS_REVISION) // initial load
      .mockResolvedValueOnce({ ...WBS_REVISION, revision_number: 3 });

    const onUpdate = vi.fn();
    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={onUpdate} docType="execution_plan" />);

    await screen.findByDisplayValue('분석 및 설계');
    fireEvent.click(screen.getByText('수정 저장 및 비교'));
    await screen.findByText('수정 패턴 학습');
    fireEvent.click(screen.getByText('수정 패턴 학습'));
    await screen.findByText('새 스타일 적용 및 재생성');
    fireEvent.click(screen.getByText('새 스타일 적용 및 재생성'));

    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledWith('proj1', { doc_type: 'execution_plan' });
    });
  });

  it('shows WBS error when no execution_plan revision exists', async () => {
    mockGetRevision.mockRejectedValue(new Error('not found'));
    render(<ReviewStage projectId="proj1" project={PROJECT} onProjectUpdate={noop} docType="execution_plan" />);

    expect(await screen.findByText(/먼저 수행계획서를 생성해주세요/)).toBeInTheDocument();
  });
});
