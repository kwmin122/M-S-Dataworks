import {
  AlertSettings,
  AnalyzeResponse,
  BidNotice,
  BidSearchResponse,
  ChatResponse,
  CompanyProfile,
  EvalBatchResponse,
  EvalJob,
  NaraAttachment,
  ProposalSections,
  SessionStats,
} from '../types';

const API_BASE_URL = (
  import.meta.env.VITE_KIRA_API_BASE_URL?.trim()
  || (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://localhost:8000')
).replace(/\/+$/, '');

async function fetchWithError(input: RequestInfo | URL, init?: RequestInit & { timeoutMs?: number }): Promise<Response> {
  const { timeoutMs, ...fetchInit } = (init || {}) as RequestInit & { timeoutMs?: number };
  const controller = new AbortController();
  const timeout = timeoutMs ?? 120_000; // 기본 2분
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    return await fetch(input, { ...fetchInit, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.');
    }
    throw new Error('서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.');
  } finally {
    clearTimeout(timer);
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = '요청 처리 중 오류가 발생했습니다.';
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string' && data.detail.trim()) {
        detail = data.detail;
      }
    } catch {
      // noop
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function createSession(): Promise<string> {
  const response = await fetchWithError(`${API_BASE_URL}/api/session`, {
    method: 'POST',
  });
  const data = await parseJson<{ session_id: string }>(response);
  return data.session_id;
}

export async function getSessionStats(sessionId: string): Promise<SessionStats> {
  const response = await fetchWithError(`${API_BASE_URL}/api/session/stats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<SessionStats>(response);
}

export async function uploadCompanyDocuments(sessionId: string, files: File[]): Promise<{ company_chunks: number; added_chunks: number; fileUrls?: string[] }> {
  const form = new FormData();
  form.append('session_id', sessionId);
  files.forEach((file) => form.append('files', file));

  const response = await fetchWithError(`${API_BASE_URL}/api/company/upload`, {
    method: 'POST',
    body: form,
  });
  return parseJson<{ company_chunks: number; added_chunks: number; fileUrls?: string[] }>(response);
}

export async function clearCompanyDocuments(sessionId: string): Promise<{ company_chunks: number }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/company/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<{ company_chunks: number }>(response);
}

export async function analyzeDocument(sessionId: string, file: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append('session_id', sessionId);
  form.append('file', file);

  const response = await fetchWithError(`${API_BASE_URL}/api/analyze/upload`, {
    method: 'POST',
    body: form,
    timeoutMs: 180_000, // 3분 — 파일 업로드 + AI 분석 소요
  });
  return parseJson<AnalyzeResponse>(response);
}

export async function chatWithReferences(sessionId: string, message: string): Promise<ChatResponse> {
  const response = await fetchWithError(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  return parseJson<ChatResponse>(response);
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

// ── 일반 대화 (세션 없이) ──

export async function generalChat(
  message: string,
  history: { role: string; content: string }[] = [],
): Promise<{ answer: string }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/chat/general`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  });
  return parseJson<{ answer: string }>(res);
}

// ── 재매칭 (회사 문서 등록 후) ──

export async function rematchWithCompanyDocs(sessionId: string): Promise<AnalyzeResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/rematch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<AnalyzeResponse>(res);
}

// ── 공고 검색 API (레거시 백엔드 → 나라장터) ──

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function searchBids(conditions: Record<string, any>): Promise<BidSearchResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/bids/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(conditions),
  });
  return parseJson<BidSearchResponse>(res);
}

export async function getBidAttachments(bidNtceNo: string, bidNtceOrd?: string): Promise<NaraAttachment[]> {
  const params = new URLSearchParams({ bid_ntce_ord: bidNtceOrd || '00' });
  const res = await fetchWithError(`${API_BASE_URL}/api/bids/${bidNtceNo}/attachments?${params}`, {
    method: 'GET',
  });
  const data = await parseJson<{ attachments: NaraAttachment[] }>(res);
  return data.attachments;
}

export async function analyzeBidFromNara(sessionId: string, bidNtceNo: string, bidNtceOrd?: string, category?: string): Promise<AnalyzeResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/bids/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      bid_ntce_no: bidNtceNo,
      bid_ntce_ord: bidNtceOrd || '00',
      category: category || '',
    }),
    timeoutMs: 180_000, // 3분 — 첨부파일 다운로드 + AI 분석 소요
  });
  return parseJson<AnalyzeResponse>(res);
}

// ── 일괄 평가 (레거시 백엔드) ──

export async function evaluateBatch(sessionId: string, bidNoticeIds: string[]): Promise<EvalBatchResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/bids/evaluate-batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, bid_ntce_nos: bidNoticeIds }),
  });
  return parseJson<EvalBatchResponse>(res);
}

export async function exportEvaluations(): Promise<void> {
  window.open('/api/export/evaluations', '_blank');
}

export async function generateProposal(bidNoticeId: string): Promise<{ sections: ProposalSections }> {
  const res = await fetch('/api/proposals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ bidNoticeId }),
  });
  return parseJson<{ sections: ProposalSections }>(res);
}

export async function generateProposalDraft(sessionId: string, bidNoticeId: string): Promise<{ sections: ProposalSections }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, bid_notice_id: bidNoticeId }),
  });
  return parseJson<{ sections: ProposalSections }>(res);
}

export async function getStrengthCard(bidNoticeId: string): Promise<unknown> {
  const res = await fetch(`/api/strength-card/${bidNoticeId}`, {
    credentials: 'include',
  });
  return parseJson<unknown>(res);
}

// ── 알림 설정 CRUD ──

export async function saveAlertSettings(sessionId: string, settings: AlertSettings): Promise<{ ok: boolean }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/alerts/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, ...settings }),
  });
  return parseJson<{ ok: boolean }>(res);
}

export async function getAlertSettings(sessionId: string): Promise<AlertSettings | null> {
  const res = await fetchWithError(`${API_BASE_URL}/api/alerts/settings?session_id=${sessionId}`, {
    method: 'GET',
  });
  const data = await parseJson<{ settings: AlertSettings | null }>(res);
  return data.settings;
}

// ── Dashboard APIs ──

export interface DashboardSummary {
  newMatches: number;
  deadlineSoon: number;
  goCount: number;
  totalAnalyzed: number;
  recentSearches: string[];
  smartFitTop5: unknown[];
}

export async function getDashboardSummary(sessionId: string): Promise<DashboardSummary> {
  const response = await fetchWithError(`${API_BASE_URL}/api/dashboard/summary?session_id=${encodeURIComponent(sessionId)}`);
  return parseJson<DashboardSummary>(response);
}

export interface SmartFitBreakdown {
  qualification: { score: number; maxScore: number; details: string };
  keywords: { score: number; maxScore: number; details: string };
  region: { score: number; maxScore: number; details: string };
  experience: { score: number; maxScore: number; details: string };
}

export interface SmartFitResult {
  totalScore: number;
  breakdown: SmartFitBreakdown;
}

export async function getSmartFitScore(
  sessionId: string,
  bidNoticeId: string,
  bidTitle: string,
  keywords: string[],
): Promise<SmartFitResult> {
  const response = await fetchWithError(`${API_BASE_URL}/api/smart-fit/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, bid_notice_id: bidNoticeId, bid_title: bidTitle, keywords }),
  });
  return parseJson<SmartFitResult>(response);
}

// ── Alert Config APIs ──

export interface AlertRule {
  id: string;
  keywords: string[];
  excludeKeywords: string[];
  categories: string[];
  regions: string[];
  minAmt?: number;
  maxAmt?: number;
  enabled: boolean;
}

export interface AlertConfig {
  enabled: boolean;
  email: string;
  schedule: 'realtime' | 'daily_1' | 'daily_2' | 'daily_3';
  hours: number[];
  rules: AlertRule[];
}

export async function getAlertConfig(sessionId: string): Promise<AlertConfig> {
  const response = await fetchWithError(`${API_BASE_URL}/api/alerts/config?session_id=${encodeURIComponent(sessionId)}`);
  return parseJson<AlertConfig>(response);
}

export async function saveAlertConfig(sessionId: string, config: AlertConfig): Promise<{ ok: boolean }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/alerts/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, ...config }),
  });
  return parseJson<{ ok: boolean }>(response);
}

// ── Forecast APIs ──

export interface OrderPlan {
  id: string;
  bizNm: string;
  orderInsttNm: string;
  orderYear: string;
  orderMnth: string;
  orderAmt: number;
  sumOrderAmt: number;
  prcrmntMethd: string;
  cntrctMthdNm: string;
  deptNm: string;
  ofclNm: string;
  telNo: string;
  category: string;
  bidNtceNoList: string;
  ntcePblancYn: string;
  bsnsTyNm: string;
  jrsdctnDivNm: string;
  totlmngInsttNm: string;
  cnstwkRgnNm: string;
  usgCntnts: string;
  specCntnts: string;
  rmrkCntnts: string;
  nticeDt: string;
  chgDt: string;
  prdctClsfcNoNm: string;
}

export interface ForecastOrgData {
  orgName: string;
  monthlyPattern: Record<string, { count: number; totalAmt: number }>;
  categoryBreakdown: Record<string, number>;
  recentBids: BidNotice[];
  orderPlans: OrderPlan[];
  aiInsight: string;
  total: number;
}

export async function getPopularAgencies(): Promise<{ agencies: string[] }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/forecast/popular`);
  return parseJson<{ agencies: string[] }>(response);
}

export async function getOrgForecast(orgName: string): Promise<ForecastOrgData> {
  const response = await fetchWithError(`${API_BASE_URL}/api/forecast/${encodeURIComponent(orgName)}`);
  return parseJson<ForecastOrgData>(response);
}

// ── 문서 텍스트 미리보기 ──

export interface TextPreviewPage {
  page_number: number;
  text: string;
}

export interface TextPreviewResponse {
  fileName: string;
  totalPages: number;
  pages: TextPreviewPage[];
}

export async function getFileTextPreview(fileUrl: string): Promise<TextPreviewResponse> {
  // fileUrl is like /api/files/{session}/{bucket}/{filename}
  // Extract session_id, bucket, filename from the path
  const match = fileUrl.match(/\/api\/files\/([^/]+)\/([^/]+)\/(.+)$/);
  if (!match) throw new Error('Invalid file URL format');
  const [, sessionId, bucket, filename] = match;
  const params = new URLSearchParams({ session_id: sessionId, bucket, filename: decodeURIComponent(filename) });
  const response = await fetchWithError(`${API_BASE_URL}/api/preview/text?${params}`);
  return parseJson<TextPreviewResponse>(response);
}

// ── 회사 프로필 API ──

export async function getCompanyProfile(): Promise<CompanyProfile | null> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'GET',
    credentials: 'include',
  });
  const data = await parseJson<{ profile: CompanyProfile | null }>(res);
  return data.profile;
}

export async function uploadCompanyProfileDocs(files: File[]): Promise<CompanyProfile> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const res = await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'POST',
    credentials: 'include',
    body: form,
    timeoutMs: 180_000,
  });
  const data = await parseJson<{ profile: CompanyProfile }>(res);
  return data.profile;
}

export async function updateCompanyProfile(updates: Partial<CompanyProfile>): Promise<CompanyProfile> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  const data = await parseJson<{ profile: CompanyProfile }>(res);
  return data.profile;
}

export async function deleteCompanyProfile(): Promise<void> {
  await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'DELETE',
    credentials: 'include',
  });
}

export async function deleteCompanyDocument(docId: string): Promise<CompanyProfile> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company/documents/${docId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  const data = await parseJson<{ profile: CompanyProfile }>(res);
  return data.profile;
}

export async function reanalyzeCompanyProfile(): Promise<CompanyProfile> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company/reanalyze`, {
    method: 'POST',
    credentials: 'include',
    timeoutMs: 180_000,
  });
  const data = await parseJson<{ profile: CompanyProfile }>(res);
  return data.profile;
}
