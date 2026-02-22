import { buildEvaluationExcel } from '../buildEvaluationExcel';

const mockRows = [
  {
    title: '경기도 CCTV 교체',
    estimatedAmt: null,
    deadlineAt: new Date('2026-03-15'),
    region: '경기',
    isEligible: true,
    evaluationReason: 'GO 판정',
    actionPlan: '실적증명서 준비',
    url: 'https://g2b.go.kr/1',
  },
];

describe('buildEvaluationExcel', () => {
  it('Buffer를 반환한다', async () => {
    const buf = await buildEvaluationExcel(mockRows);
    expect(buf).toBeInstanceOf(Buffer);
    expect(buf.length).toBeGreaterThan(0);
  });

  it('빈 배열도 처리한다', async () => {
    const buf = await buildEvaluationExcel([]);
    expect(buf).toBeInstanceOf(Buffer);
  });
});
