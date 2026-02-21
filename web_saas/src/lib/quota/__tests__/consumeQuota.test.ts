import { getMaxCountForPlan, FREE_PLAN_LIMIT } from '../consumeQuota';

describe('getMaxCountForPlan', () => {
  it('returns -1 for PRO plan', () => {
    expect(getMaxCountForPlan('PRO')).toBe(-1);
  });

  it('returns FREE_PLAN_LIMIT for FREE plan', () => {
    expect(getMaxCountForPlan('FREE')).toBe(FREE_PLAN_LIMIT);
  });

  it('returns FREE_PLAN_LIMIT when plan is null (no subscription)', () => {
    expect(getMaxCountForPlan(null)).toBe(FREE_PLAN_LIMIT);
  });
});
