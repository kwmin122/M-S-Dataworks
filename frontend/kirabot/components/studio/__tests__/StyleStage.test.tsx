import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import StyleStage from '../stages/StyleStage';
import type { StyleSkill } from '../../../services/studioApi';

vi.mock('../../../services/studioApi', async () => {
  const actual = await vi.importActual('../../../services/studioApi');
  return {
    ...actual,
    listStyleSkills: vi.fn(),
    createStyleSkill: vi.fn(),
    pinStyleSkill: vi.fn(),
    unpinStyleSkill: vi.fn(),
    deriveStyleSkill: vi.fn(),
    promoteStyleSkill: vi.fn(),
  };
});

import {
  listStyleSkills, createStyleSkill, pinStyleSkill,
  unpinStyleSkill, promoteStyleSkill,
} from '../../../services/studioApi';
const mockListSkills = vi.mocked(listStyleSkills);
const mockCreateSkill = vi.mocked(createStyleSkill);
const mockPinSkill = vi.mocked(pinStyleSkill);
const mockUnpinSkill = vi.mocked(unpinStyleSkill);
const mockPromoteSkill = vi.mocked(promoteStyleSkill);

const SAMPLE_SKILLS: StyleSkill[] = [
  {
    id: 'sk1', project_id: 'proj1', version: 1, name: '경어체 스타일',
    source_type: 'uploaded', derived_from_id: null,
    profile_md_content: '# 문체 프로필\n- 경어체 사용', style_json: { tone: 'formal' },
    is_shared_default: false, created_at: '2026-03-18T10:00:00Z',
  },
  {
    id: 'sk2', project_id: 'proj1', version: 2, name: '수정 스타일 v2',
    source_type: 'derived', derived_from_id: 'sk1',
    profile_md_content: null, style_json: { tone: 'casual' },
    is_shared_default: false, created_at: '2026-03-18T11:00:00Z',
  },
  {
    id: 'sk-shared', project_id: null, version: 1, name: '조직 기본 스타일',
    source_type: 'promoted', derived_from_id: 'sk1',
    profile_md_content: '# 조직 기본', style_json: null,
    is_shared_default: true, created_at: '2026-03-18T09:00:00Z',
  },
];

const noop = () => {};

describe('StyleStage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('renders project and shared skills', async () => {
    mockListSkills.mockResolvedValue(SAMPLE_SKILLS);
    render(<StyleStage projectId="proj1" pinnedStyleSkillId={null} onProjectUpdate={noop} />);

    expect(await screen.findByText('경어체 스타일')).toBeInTheDocument();
    expect(screen.getByText('수정 스타일 v2')).toBeInTheDocument();
    expect(screen.getByText('조직 기본 스타일')).toBeInTheDocument();

    // Section headers
    expect(screen.getByText('프로젝트 스타일')).toBeInTheDocument();
    expect(screen.getByText('조직 공유 스타일')).toBeInTheDocument();
  });

  it('shows pinned indicator when skill is pinned', async () => {
    mockListSkills.mockResolvedValue(SAMPLE_SKILLS);
    render(<StyleStage projectId="proj1" pinnedStyleSkillId="sk1" onProjectUpdate={noop} />);

    // Name appears in both pinned indicator and skill card
    const matches = await screen.findAllByText('경어체 스타일');
    expect(matches.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('핀 설정됨:')).toBeInTheDocument();
    // Pin badge on the card
    expect(screen.getByText('핀')).toBeInTheDocument();
  });

  it('calls pinStyleSkill on pin button click', async () => {
    mockListSkills.mockResolvedValue(SAMPLE_SKILLS);
    mockPinSkill.mockResolvedValue({ pinned_style_skill_id: 'sk2' });
    const onUpdate = vi.fn();

    render(<StyleStage projectId="proj1" pinnedStyleSkillId={null} onProjectUpdate={onUpdate} />);
    await screen.findByText('경어체 스타일');

    // Find pin buttons (title="핀 설정")
    const pinButtons = screen.getAllByTitle('핀 설정');
    expect(pinButtons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(pinButtons[0]);

    await waitFor(() => {
      expect(mockPinSkill).toHaveBeenCalledWith('proj1', 'sk1');
      expect(onUpdate).toHaveBeenCalled();
    });
  });

  it('calls unpinStyleSkill on unpin click', async () => {
    mockListSkills.mockResolvedValue(SAMPLE_SKILLS);
    mockUnpinSkill.mockResolvedValue({ pinned_style_skill_id: null });
    const onUpdate = vi.fn();

    render(<StyleStage projectId="proj1" pinnedStyleSkillId="sk1" onProjectUpdate={onUpdate} />);
    await screen.findByText('핀 설정됨:');

    fireEvent.click(screen.getByText('해제'));

    await waitFor(() => {
      expect(mockUnpinSkill).toHaveBeenCalledWith('proj1');
      expect(onUpdate).toHaveBeenCalled();
    });
  });

  it('creates new style via form', async () => {
    mockListSkills.mockResolvedValue([]);
    mockCreateSkill.mockResolvedValue({
      id: 'new-sk', project_id: 'proj1', version: 1, name: '새 스타일',
      source_type: 'uploaded', derived_from_id: null,
      profile_md_content: null, style_json: null,
      is_shared_default: false, created_at: '2026-03-18T12:00:00Z',
    });

    render(<StyleStage projectId="proj1" pinnedStyleSkillId={null} onProjectUpdate={noop} />);
    await screen.findByText('새 스타일');

    // Click "새 스타일" button
    fireEvent.click(screen.getByText('새 스타일'));

    const nameInput = screen.getByLabelText('스타일 이름');
    fireEvent.change(nameInput, { target: { value: '테스트 스타일' } });

    fireEvent.click(screen.getByText('저장'));

    await waitFor(() => {
      expect(mockCreateSkill).toHaveBeenCalledWith('proj1', {
        name: '테스트 스타일',
        profile_md_content: undefined,
      });
    });
  });

  it('calls promoteStyleSkill on promote button click', async () => {
    mockListSkills.mockResolvedValue(SAMPLE_SKILLS);
    mockPromoteSkill.mockResolvedValue({ promoted: true, shared_skill_id: 'new-shared' });

    render(<StyleStage projectId="proj1" pinnedStyleSkillId={null} onProjectUpdate={noop} />);
    await screen.findByText('경어체 스타일');

    const promoteButtons = screen.getAllByTitle('조직 기본값으로 승격');
    expect(promoteButtons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(promoteButtons[0]);

    await waitFor(() => {
      expect(mockPromoteSkill).toHaveBeenCalledWith('proj1', 'sk1');
    });
  });

  it('shows error state', async () => {
    mockListSkills.mockRejectedValue(new Error('서버 오류'));
    render(<StyleStage projectId="proj1" pinnedStyleSkillId={null} onProjectUpdate={noop} />);

    expect(await screen.findByText('서버 오류')).toBeInTheDocument();
    expect(screen.getByText('다시 시도')).toBeInTheDocument();
  });
});
