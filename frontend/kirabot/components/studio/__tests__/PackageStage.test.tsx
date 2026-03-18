import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import PackageStage from '../stages/PackageStage';
import type { PackageItem } from '../../../services/studioApi';

// Mock the studioApi module
vi.mock('../../../services/studioApi', async () => {
  const actual = await vi.importActual('../../../services/studioApi');
  return {
    ...actual,
    listPackageItems: vi.fn(),
  };
});

import { listPackageItems } from '../../../services/studioApi';
const mockListPackageItems = vi.mocked(listPackageItems);

const SAMPLE_ITEMS: PackageItem[] = [
  { id: '1', package_category: 'generated_document', document_code: 'proposal', document_label: '기술 제안서', required: true, status: 'ready_to_generate', generation_target: 'proposal', sort_order: 1 },
  { id: '2', package_category: 'generated_document', document_code: 'execution_plan', document_label: '수행계획서/WBS', required: true, status: 'ready_to_generate', generation_target: 'execution_plan', sort_order: 2 },
  { id: '3', package_category: 'evidence', document_code: 'experience_cert', document_label: '용역수행실적확인서', required: true, status: 'missing', generation_target: null, sort_order: 10 },
  { id: '4', package_category: 'evidence', document_code: 'business_license', document_label: '사업자등록증', required: true, status: 'missing', generation_target: null, sort_order: 100 },
  { id: '5', package_category: 'administrative', document_code: 'bid_letter', document_label: '입찰서', required: true, status: 'missing', generation_target: null, sort_order: 200 },
  { id: '6', package_category: 'price', document_code: 'price_proposal', document_label: '가격제안서', required: true, status: 'missing', generation_target: null, sort_order: 50 },
];

describe('PackageStage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all 4 category groups when items exist', async () => {
    mockListPackageItems.mockResolvedValue(SAMPLE_ITEMS);
    render(<PackageStage projectId="test-proj" />);

    // Wait for loading to finish
    expect(await screen.findByText('기술 제안서')).toBeInTheDocument();

    // All 4 groups visible
    expect(screen.getByText('자동 생성 문서')).toBeInTheDocument();
    expect(screen.getByText('증빙 서류')).toBeInTheDocument();
    expect(screen.getByText('행정 서류')).toBeInTheDocument();
    expect(screen.getByText('가격 서류')).toBeInTheDocument();
  });

  it('shows empty state when no items', async () => {
    mockListPackageItems.mockResolvedValue([]);
    render(<PackageStage projectId="test-proj" />);

    expect(await screen.findByText('아직 분류된 패키지 항목이 없습니다.')).toBeInTheDocument();
  });

  it('shows ready_to_generate badge for generated documents', async () => {
    mockListPackageItems.mockResolvedValue(SAMPLE_ITEMS);
    render(<PackageStage projectId="test-proj" />);

    await screen.findByText('기술 제안서');
    // ready_to_generate items show "생성 가능" badge
    const badges = screen.getAllByText('생성 가능');
    expect(badges.length).toBe(2); // proposal + execution_plan

    // missing items show "미제출" badge
    const missingBadges = screen.getAllByText('미제출');
    expect(missingBadges.length).toBeGreaterThanOrEqual(3);
  });

  it('calculates progress correctly', async () => {
    const itemsWithCompleted: PackageItem[] = [
      ...SAMPLE_ITEMS.slice(0, 2),
      { ...SAMPLE_ITEMS[2], status: 'uploaded' }, // 1 completed
    ];
    mockListPackageItems.mockResolvedValue(itemsWithCompleted);
    render(<PackageStage projectId="test-proj" />);

    await screen.findByText('기술 제안서');
    expect(screen.getByText('1/3 완료')).toBeInTheDocument();
  });

  it('shows domain and method labels when provided', async () => {
    mockListPackageItems.mockResolvedValue(SAMPLE_ITEMS);
    render(
      <PackageStage
        projectId="test-proj"
        procurementDomain="service"
        contractMethod="negotiated"
      />,
    );

    await screen.findByText('기술 제안서');
    expect(screen.getByText('용역 / 협상에 의한 계약')).toBeInTheDocument();
  });
});
