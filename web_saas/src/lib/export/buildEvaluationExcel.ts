import ExcelJS from 'exceljs';

interface EvalRow {
  title: string;
  estimatedAmt: bigint | null;
  deadlineAt: Date | null;
  region: string | null;
  isEligible: boolean | null;
  evaluationReason: string;
  actionPlan: string | null;
  url: string | null;
}

const HEADERS = [
  '공고명', '금액(원)', '마감일', '지역', 'GO/NO-GO', '판정근거', '준비액션', '공고URL',
];

export async function buildEvaluationExcel(rows: EvalRow[]): Promise<ArrayBuffer> {
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet('공고 분석 결과');

  ws.addRow(HEADERS);
  ws.getRow(1).font = { bold: true };

  for (const r of rows) {
    ws.addRow([
      r.title,
      r.estimatedAmt != null ? Number(r.estimatedAmt) : '',
      r.deadlineAt ? r.deadlineAt.toISOString().slice(0, 10) : '',
      r.region ?? '',
      r.isEligible === true ? 'GO' : r.isEligible === false ? 'NO-GO' : '미평가',
      r.evaluationReason,
      r.actionPlan ?? '',
      r.url ?? '',
    ]);
  }

  const bytes = new Uint8Array(await wb.xlsx.writeBuffer());
  const out = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(out).set(bytes);
  return out;
}
