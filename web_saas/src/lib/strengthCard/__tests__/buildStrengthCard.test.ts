import { matchStrengths } from '../buildStrengthCard';

describe('matchStrengths', () => {
  const companyFacts = {
    licenses: ['정보통신공사업', '전기공사업'],
    region: '경기',
    certifications: ['CC인증'],
    revenue: 500000000,
  };

  it('면허 보유 시 strengths에 포함', () => {
    const { strengths, gaps } = matchStrengths(companyFacts, {
      requiredLicenses: ['정보통신공사업'],
      region: '경기',
      minRevenue: 300000000,
    });
    expect(strengths.some((s) => s.includes('정보통신'))).toBe(true);
    expect(gaps).toHaveLength(0);
  });

  it('면허 미보유 시 gaps에 포함', () => {
    const { gaps } = matchStrengths(companyFacts, {
      requiredLicenses: ['건설업면허'],
      region: '경기',
    });
    expect(gaps.some((g) => g.includes('건설업'))).toBe(true);
  });
});
