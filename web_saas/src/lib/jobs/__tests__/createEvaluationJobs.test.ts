import { matchesInterestConfig } from '../createEvaluationJobs';

describe('matchesInterestConfig', () => {
  const notice = { title: 'CCTV 설치 공사', category: '정보통신', region: '경기도' };

  it('returns true when keyword matches title', () => {
    expect(matchesInterestConfig({ keywords: ['CCTV'], regions: [] }, notice)).toBe(true);
  });

  it('returns true when keyword matches category', () => {
    expect(matchesInterestConfig({ keywords: ['정보통신'], regions: [] }, notice)).toBe(true);
  });

  it('returns false when keyword has no match', () => {
    expect(matchesInterestConfig({ keywords: ['소방'], regions: [] }, notice)).toBe(false);
  });

  it('returns false when region mismatches', () => {
    expect(matchesInterestConfig({ keywords: ['CCTV'], regions: ['서울특별시'] }, notice)).toBe(false);
  });

  it('returns true when regions is empty (전국)', () => {
    expect(matchesInterestConfig({ keywords: ['CCTV'], regions: [] }, notice)).toBe(true);
  });

  it('returns false when interestConfig is null', () => {
    expect(matchesInterestConfig(null, notice)).toBe(false);
  });
});
