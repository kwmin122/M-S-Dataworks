import { buildSearchConditions } from '../buildSearchQuery';

describe('buildSearchConditions', () => {
  it('빈 조건이면 빈 where 반환', () => {
    const result = buildSearchConditions({});
    expect(result).toEqual({});
  });

  it('keywords 배열로 title OR 조건 생성', () => {
    const result = buildSearchConditions({ keywords: ['CCTV', '통신'] });
    expect(result.OR).toHaveLength(2);
    expect((result.OR as Array<Record<string, unknown>>)[0]).toEqual({ title: { contains: 'CCTV', mode: 'insensitive' } });
  });

  it('region 필터 포함', () => {
    const result = buildSearchConditions({ region: '경기' });
    expect(result.region).toEqual({ contains: '경기', mode: 'insensitive' });
  });

  it('excludeExpired=true이면 deadlineAt > now() 조건', () => {
    const before = new Date();
    const result = buildSearchConditions({ excludeExpired: true });
    const deadlineCondition = result.deadlineAt as { gt: Date };
    expect(deadlineCondition?.gt).toBeInstanceOf(Date);
    expect(deadlineCondition.gt >= before).toBe(true);
  });
});
