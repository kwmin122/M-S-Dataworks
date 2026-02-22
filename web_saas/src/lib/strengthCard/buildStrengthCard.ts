interface CompanyFacts {
  licenses?: string[];
  region?: string;
  certifications?: string[];
  revenue?: number;
}

interface BidRequirements {
  requiredLicenses?: string[];
  region?: string;
  minRevenue?: number;
}

export function matchStrengths(
  company: CompanyFacts,
  requirements: BidRequirements,
): { strengths: string[]; gaps: string[] } {
  const strengths: string[] = [];
  const gaps: string[] = [];

  for (const lic of requirements.requiredLicenses ?? []) {
    if (company.licenses?.some((l) => l.includes(lic) || lic.includes(l))) {
      strengths.push(`${lic} 면허 보유`);
    } else {
      gaps.push(`${lic} 면허 미보유 (공고 요건: 필수)`);
    }
  }

  if (requirements.region && company.region === requirements.region) {
    strengths.push(`${requirements.region} 지역 활동 이력`);
  }

  if (requirements.minRevenue && company.revenue) {
    if (company.revenue >= requirements.minRevenue) {
      strengths.push(`매출 기준 충족 (${(company.revenue / 100000000).toFixed(1)}억원)`);
    } else {
      gaps.push(`매출 기준 미충족 (요건: ${(requirements.minRevenue / 100000000).toFixed(1)}억원 이상)`);
    }
  }

  return { strengths, gaps };
}
