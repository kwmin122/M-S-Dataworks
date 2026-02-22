import { buildFtsQuery } from '../ftsSearch';

describe('buildFtsQuery', () => {
  it('단일 키워드 tsquery 생성', () => {
    expect(buildFtsQuery(['CCTV'])).toBe('CCTV');
  });

  it('다중 키워드 OR 연결', () => {
    expect(buildFtsQuery(['CCTV', '통신'])).toBe('CCTV | 통신');
  });

  it('빈 배열이면 빈 문자열', () => {
    expect(buildFtsQuery([])).toBe('');
  });

  it('특수문자 제거', () => {
    expect(buildFtsQuery(["CCTV's"])).toBe('CCTVs');
  });
});
