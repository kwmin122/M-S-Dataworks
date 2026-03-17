import {
  AnalyzeResponse,
  BidNotice,
  BidSearchResponse,
  ChatResponse,
  ChecklistItem,
  CompanyDocInfo,
  CompanyProfile,
  EvalBatchResponse,
  EvalJob,
  NaraAttachment,
  PersonnelInput,
  ProfileHistoryResponse,
  ProfileMdResponse,
  ProposalSections,
  ProposalSectionsResponse,
  SessionStats,
  Subscription,
  TrackRecordInput,
} from '../types';

const API_BASE_URL = (
  import.meta.env.VITE_KIRA_API_BASE_URL?.trim()
  || (typeof window !== 'undefined' && window.location.hostname !== 'localhost'
    ? window.location.origin
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

/**
 * Sanitize a company name into a safe company_id.
 * Backend allows only [a-zA-Z0-9가-힣._-], so strip everything else.
 */
export function sanitizeCompanyId(name: string): string {
  const sanitized = name.replace(/[^a-zA-Z0-9가-힣._\-]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
  return sanitized || '_default';
}

export async function createSession(): Promise<string> {
  const response = await fetchWithError(`${API_BASE_URL}/api/session`, {
    method: 'POST',
  });
  const data = await parseJson<{ session_id: string }>(response);
  return data.session_id;
}

export interface SessionCheckResult {
  session_id: string;
  exists: boolean;
  has_analysis: boolean;
  analysis_title: string | null;
}

export async function checkSession(sessionId: string): Promise<SessionCheckResult> {
  const response = await fetchWithError(`${API_BASE_URL}/api/session/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<SessionCheckResult>(response);
}

export async function getSessionStats(sessionId: string): Promise<SessionStats> {
  const response = await fetchWithError(`${API_BASE_URL}/api/session/stats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<SessionStats>(response);
}

export async function uploadCompanyDocuments(sessionId: string, files: File[]): Promise<{ company_chunks: number; added_chunks: number; fileUrls?: string[]; documents?: CompanyDocInfo[] }> {
  const form = new FormData();
  form.append('session_id', sessionId);
  files.forEach((file) => form.append('files', file));

  const response = await fetchWithError(`${API_BASE_URL}/api/company/upload`, {
    method: 'POST',
    body: form,
  });
  return parseJson<{ company_chunks: number; added_chunks: number; fileUrls?: string[]; documents?: CompanyDocInfo[] }>(response);
}

export async function uploadCompanyText(sessionId: string, text: string): Promise<{ company_chunks: number; added_chunks: number; documents?: CompanyDocInfo[] }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/company/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, text }),
  });
  return parseJson<{ company_chunks: number; added_chunks: number; documents?: CompanyDocInfo[] }>(response);
}

export async function clearCompanyDocuments(sessionId: string): Promise<{ company_chunks: number }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/company/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<{ company_chunks: number }>(response);
}

export async function listCompanyDocuments(sessionId: string): Promise<{ documents: CompanyDocInfo[]; total_chunks: number }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/company/list?session_id=${encodeURIComponent(sessionId)}`);
  return parseJson<{ documents: CompanyDocInfo[]; total_chunks: number }>(response);
}

export async function deleteSessionCompanyDocument(sessionId: string, sourceFile: string): Promise<{ deleted_chunks: number; remaining_chunks: number }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/company/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, source_file: sourceFile }),
  });
  return parseJson<{ deleted_chunks: number; remaining_chunks: number }>(response);
}

export async function analyzeDocument(sessionId: string, files: File | File[]): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append('session_id', sessionId);
  const fileArray = Array.isArray(files) ? files : [files];
  for (const f of fileArray) {
    form.append('files', f);
  }

  const response = await fetchWithError(`${API_BASE_URL}/api/analyze/upload`, {
    method: 'POST',
    body: form,
    timeoutMs: 180_000, // 3분 — 파일 업로드 + AI 분석 소요
  });
  return parseJson<AnalyzeResponse>(response);
}

export async function chatWithReferences(sessionId: string, message: string, sourceFiles?: string[]): Promise<ChatResponse & { scoped_to?: string[] }> {
  const body: Record<string, unknown> = { session_id: sessionId, message };
  if (sourceFiles?.length) body.source_files = sourceFiles;
  const response = await fetchWithError(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return parseJson<ChatResponse & { scoped_to?: string[] }>(response);
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
  const res = await fetchWithError(`${API_BASE_URL}/api/export/evaluations`, {
    method: 'GET',
    credentials: 'include',
  });
  if (!res.ok) {
    throw new Error('평가 결과 내보내기에 실패했습니다.');
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const disposition = res.headers.get('Content-Disposition');
  a.download = disposition?.match(/filename="?(.+?)"?$/)?.[1] || 'evaluations.xlsx';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
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

// ── A-lite 제안서 DOCX 생성 (Layer 1 knowledge-augmented) ──

export interface ProposalV2Section {
  name: string;
  preview: string;
}

export interface ProposalV2QualityIssue {
  category: string;
  severity: string;
  detail: string;
}

export interface ProposalV2Response {
  docx_filename: string;
  hwpx_filename: string;
  output_filename: string;
  sections: ProposalV2Section[];
  quality_issues: ProposalV2QualityIssue[];
  generation_time_sec: number;
}

export async function generateProposalV2(
  sessionId: string,
  totalPages: number = 50,
  outputFormat: 'docx' | 'hwpx' = 'docx',
  companyId?: string,
): Promise<ProposalV2Response> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal/generate-v2`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, total_pages: totalPages, output_format: outputFormat, company_id: companyId || '_default' }),
    timeoutMs: 300_000, // 5분 — DOCX/HWPX 생성 시간 소요
  });
  return parseJson<ProposalV2Response>(res);
}

export const getProposalDownloadUrl = getFileDownloadUrl;

// ── 체크리스트 API ──

export interface ChecklistResponse {
  items: ChecklistItem[];
  total: number;
  mandatory_count: number;
}

export async function getChecklist(sessionId: string): Promise<ChecklistResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal/checklist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
    timeoutMs: 60_000,
  });
  return parseJson<ChecklistResponse>(res);
}

// ── Phase 2: WBS / PPT / 실적기술서 API ──

export interface WbsTaskItem {
  phase: string;
  task_name: string;
  start_month: number;
  duration_months: number;
  responsible_role: string;
}

export interface WbsResponse {
  xlsx_filename: string;
  gantt_filename: string;
  docx_filename: string;
  tasks_count: number;
  total_months: number;
  generation_time_sec: number;
  methodology?: string;
  tasks?: WbsTaskItem[];
}

export async function generateExecutionPlan(
  sessionId: string,
  methodology?: string,
  usePack?: boolean,
  companyId?: string,
): Promise<WbsResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal/generate-wbs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      methodology: methodology || '',
      use_pack: usePack || false,
      company_id: companyId || '_default',
    }),
    timeoutMs: 300_000,
  });
  return parseJson<WbsResponse>(res);
}

export interface PptQnaPair {
  question: string;
  answer: string;
  category: string;
}

export interface PptResponse {
  pptx_filename: string;
  slide_count: number;
  qna_pairs: PptQnaPair[];
  total_duration_min: number;
  generation_time_sec: number;
}

export async function generatePresentation(
  sessionId: string,
  durationMin: number = 30,
  qnaCount: number = 10,
  companyId?: string,
): Promise<PptResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal/generate-ppt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, duration_min: durationMin, qna_count: qnaCount, company_id: companyId || '_default' }),
    timeoutMs: 300_000,
  });
  return parseJson<PptResponse>(res);
}

export interface TrackRecordDocResponse {
  docx_filename: string;
  track_record_count: number;
  personnel_count: number;
  generation_time_sec: number;
}

export async function generateTrackRecord(
  sessionId: string,
  companyId?: string,
): Promise<TrackRecordDocResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal/generate-track-record`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, company_id: companyId || '_default' }),
    timeoutMs: 300_000,
  });
  return parseJson<TrackRecordDocResponse>(res);
}

const SAFE_FILENAME_RE = /^[a-zA-Z0-9가-힣._\-]+$/;

export function getFileDownloadUrl(filename: string): string {
  if (!filename || !SAFE_FILENAME_RE.test(filename) || filename.includes('..')) {
    throw new Error(`잘못된 파일명: ${filename}`);
  }
  return `${API_BASE_URL}/api/proposal/download/${encodeURIComponent(filename)}`;
}

// ── 회사 DB 온보딩 API ──

export interface TrackRecord {
  project_name: string;
  client: string;
  contract_amount: string;
  period: string;
  description: string;
}

export interface Personnel {
  name: string;
  role: string;
  experience_years: number;
  certifications: string[];
  description: string;
}

export interface CompanyDbProfile {
  company_name: string;
  business_type: string;
  specializations: string[];
  employee_count: number;
  track_record_count: number;
  personnel_count: number;
}

export interface CompanyDbStats {
  track_record_count: number;
  personnel_count: number;
  total_knowledge_units: number;
}

export async function addTrackRecord(record: TrackRecordInput, companyId: string = '_default', sessionId: string = ''): Promise<{ id: string; total: number }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/track-records`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...record, company_id: companyId, session_id: sessionId }),
  });
  return parseJson<{ id: string; total: number }>(res);
}

export async function addPersonnel(person: PersonnelInput, companyId: string = '_default', sessionId: string = ''): Promise<{ id: string; total: number }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/personnel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...person, company_id: companyId, session_id: sessionId }),
  });
  return parseJson<{ id: string; total: number }>(res);
}

export async function getCompanyDbProfile(companyId: string = '_default'): Promise<CompanyDbProfile | null> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/profile?company_id=${encodeURIComponent(companyId)}`);
  const data = await parseJson<{ profile: CompanyDbProfile | null }>(res);
  return data.profile;
}

export async function updateCompanyDbProfile(updates: Partial<CompanyDbProfile>, companyId: string = '_default'): Promise<CompanyDbProfile> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...updates, company_id: companyId }),
  });
  const data = await parseJson<{ profile: CompanyDbProfile }>(res);
  return data.profile;
}

export async function getCompanyDbStats(companyId: string = '_default'): Promise<CompanyDbStats> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/stats?company_id=${encodeURIComponent(companyId)}`);
  return parseJson<CompanyDbStats>(res);
}

export async function getCanonicalCompanyId(companyName: string): Promise<string> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/canonical-id?company_name=${encodeURIComponent(companyName)}`);
  const data = await parseJson<{ company_id: string }>(res);
  return data.company_id;
}

export async function listTrackRecords(companyId: string = '_default'): Promise<{ records: import('../types').TrackRecordListItem[] }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/track-records?company_id=${encodeURIComponent(companyId)}`);
  return parseJson<{ records: import('../types').TrackRecordListItem[] }>(res);
}

export async function listPersonnel(companyId: string = '_default'): Promise<{ personnel: import('../types').PersonnelListItem[] }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/personnel?company_id=${encodeURIComponent(companyId)}`);
  return parseJson<{ personnel: import('../types').PersonnelListItem[] }>(res);
}

export async function deleteCompanyDbItem(docId: string, companyId: string = '_default', sessionId: string = ''): Promise<{ success: boolean }> {
  const params = new URLSearchParams({ company_id: companyId });
  if (sessionId) params.set('session_id', sessionId);
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/items/${encodeURIComponent(docId)}?${params.toString()}`, {
    method: 'DELETE',
  });
  return parseJson<{ success: boolean }>(res);
}

export async function getStrengthCard(bidNoticeId: string): Promise<unknown> {
  const res = await fetch(`/api/strength-card/${bidNoticeId}`, {
    credentials: 'include',
  });
  return parseJson<unknown>(res);
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

  // 🆕 New filter fields
  productCodes?: string[];              // 물품분류번호 (undefined = 필터 미사용)
  detailedItems?: string[];             // 세부품명 (undefined = 필터 미사용)
  excludeRegions?: string[];            // 제외 지역 (매칭 시 차단)
  excludeAgencyLocations?: string[];    // 제외 발주처 소재지 (매칭 시 차단)
}

export interface AlertCompanyProfile {
  description: string;                  // 자연어 회사 설명 (LLM 프롬프트용)
  businessTypes?: string[];             // 주요 업종 (선택)
  certifications?: string[];            // 보유 인증 (선택)
  mainProducts?: string[];              // 주력 제품 (선택)
  excludedAreas?: string[];             // 제외 지역/품목 (선택)
}

export interface AlertConfig {
  enabled: boolean;
  email: string;
  schedule: 'realtime' | 'daily_1' | 'daily_2' | 'daily_3';
  hours: number[];
  rules: AlertRule[];
  companyProfile?: AlertCompanyProfile; // 🆕 회사 프로필
  // Schedule details
  digestTime?: string;        // "HH:MM" format
  digestDays?: number[];      // 0=Sun..6=Sat (weekly schedule only)
  maxPerDay?: number;         // Max alerts per day (realtime only)
  quietHours?: {
    enabled: boolean;
    start: string;            // "HH:MM"
    end: string;              // "HH:MM"
    weekendOff: boolean;
  };
  createdAt?: string;                   // ISO 8601, 백엔드에서 자동 설정
  updatedAt?: string;                   // ISO 8601, 백엔드에서 자동 갱신
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

// ── Alert Config APIs (Email-based) ──

export async function getUserAlertConfig(email: string): Promise<AlertConfig> {
  const response = await fetchWithError(
    `${API_BASE_URL}/api/alerts/config?email=${encodeURIComponent(email)}`
  );
  return parseJson<AlertConfig>(response);
}

export async function saveUserAlertConfig(config: AlertConfig): Promise<{ success: boolean; message: string }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/alerts/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  return parseJson<{ success: boolean; message: string }>(response);
}

export interface AlertPreviewResult {
  count: number;
  bids: Array<{
    id: string;
    title: string;
    organization: string;
    deadline: string;
    amount?: number;
  }>;
}

export async function previewAlertMatches(rules: AlertRule[]): Promise<AlertPreviewResult> {
  const response = await fetchWithError(`${API_BASE_URL}/api/alerts/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rules }),
  });
  return parseJson<AlertPreviewResult>(response);
}

export async function testSendAlert(email: string, rules: AlertRule[]): Promise<{ ok: boolean; sent: boolean; count: number }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/alerts/test-send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, rules }),
  });
  return parseJson<{ ok: boolean; sent: boolean; count: number }>(response);
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

export interface UploadResult {
  savedCount: number;
  extractionStatus: 'skipped' | 'success' | 'partial' | 'failed' | 'no_text';
  filledFields: string[];
}

export async function uploadCompanyProfileDocs(files: File[]): Promise<{ profile: CompanyProfile; uploadResult?: UploadResult }> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const res = await fetchWithError(`${API_BASE_URL}/api/company/profile`, {
    method: 'POST',
    credentials: 'include',
    body: form,
    timeoutMs: 180_000,
  });
  const data = await parseJson<{ profile: CompanyProfile; uploadResult?: UploadResult }>(res);
  return { profile: data.profile, uploadResult: data.uploadResult };
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

// ── Payment APIs ──

export async function getSubscription(): Promise<Subscription> {
  const res = await fetchWithError(`${API_BASE_URL}/api/payments/subscription`, {
    method: 'GET',
    credentials: 'include',
  });
  const data = await parseJson<{ subscription: Subscription }>(res);
  return data.subscription;
}

export async function registerBillingKey(params: {
  billingKey: string;
  plan: string;
  cardLast4: string;
}): Promise<Subscription> {
  const res = await fetchWithError(`${API_BASE_URL}/api/payments/billing-key`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  const data = await parseJson<{ subscription: Subscription }>(res);
  return data.subscription;
}

export async function cancelSubscription(): Promise<Subscription> {
  const res = await fetchWithError(`${API_BASE_URL}/api/payments/cancel`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  const data = await parseJson<{ subscription: Subscription }>(res);
  return data.subscription;
}

export async function verifyPaymentAmount(plan: string): Promise<{ plan: string; amount: number; currency: string }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/payments/verify-amount`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan }),
  });
  return parseJson<{ plan: string; amount: number; currency: string }>(res);
}

// ── 관리자 API ──

export interface AdminUsageOverview {
  today_chat: number;
  today_analyze: number;
  month_chat: number;
  month_analyze: number;
}

export interface AdminActorUsage {
  actor_key: string;
  username: string;
  chat_count: number;
  analyze_count: number;
  last_activity: string;
}

export interface AdminUsageResponse {
  ok: boolean;
  username: string;
  overview: AdminUsageOverview;
  by_actor: AdminActorUsage[];
}

export interface AdminAlertItem {
  session_id: string;
  config: {
    enabled: boolean;
    email: string;
    schedule: string;
    hours: number[];
    rules: Array<{
      keywords: string[];
      categories: string[];
      regions: string[];
      minAmt: string | number | null;
      maxAmt: string | number | null;
      enabled: boolean;
    }>;
  };
  state: {
    last_sent?: string;
    sent_bid_ids?: string[];
    last_confirmation_sent?: string;
  };
}

export async function getAdminUsage(): Promise<AdminUsageResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/admin/usage`, {
    method: 'GET',
    credentials: 'include',
  });
  return parseJson<AdminUsageResponse>(res);
}

export async function getAdminAlerts(): Promise<AdminAlertItem[]> {
  const res = await fetchWithError(`${API_BASE_URL}/api/admin/alerts`, {
    method: 'GET',
    credentials: 'include',
  });
  const data = await parseJson<{ ok: boolean; alerts: AdminAlertItem[] }>(res);
  return data.alerts;
}

export async function deleteAdminAlert(configId: string): Promise<void> {
  await fetchWithError(`${API_BASE_URL}/api/admin/alerts/${encodeURIComponent(configId)}`, {
    method: 'DELETE',
    credentials: 'include',
  });
}

export async function sendAdminAlertNow(configId: string): Promise<{ sent: boolean; count: number; totalFound?: number; reason?: string }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/admin/alerts/${encodeURIComponent(configId)}/send-now`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  return parseJson<{ sent: boolean; count: number; totalFound?: number; reason?: string }>(res);
}

// ── Profile.md 편집 ──

export async function getProfileMd(companyId = 'default'): Promise<ProfileMdResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/profile-md?company_id=${encodeURIComponent(companyId)}`);
  return parseJson<ProfileMdResponse>(res);
}

export async function updateProfileSection(
  companyId: string, sectionName: string, content: string,
): Promise<{ success: boolean; version: number }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/profile-md/section`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_id: companyId, section_name: sectionName, content }),
  });
  return parseJson<{ success: boolean; version: number }>(res);
}

export async function getProfileHistory(companyId = 'default'): Promise<ProfileHistoryResponse> {
  const res = await fetchWithError(`${API_BASE_URL}/api/profile-md/history?company_id=${encodeURIComponent(companyId)}`);
  return parseJson<ProfileHistoryResponse>(res);
}

export async function rollbackProfile(
  companyId: string, targetVersion: number,
): Promise<{ success: boolean; restored_version?: number; error?: string }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/profile-md/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_id: companyId, target_version: targetVersion }),
  });
  return parseJson<{ success: boolean; restored_version?: number; error?: string }>(res);
}

// ── 제안서 섹션 편집 ──

export async function getProposalSections(docxFilename: string): Promise<ProposalSectionsResponse> {
  const res = await fetchWithError(
    `${API_BASE_URL}/api/proposal-sections?docx_filename=${encodeURIComponent(docxFilename)}`,
  );
  return parseJson<ProposalSectionsResponse>(res);
}

export async function updateProposalSection(
  docxFilename: string, sectionName: string, text: string,
): Promise<{ success: boolean }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal-sections`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ docx_filename: docxFilename, section_name: sectionName, text }),
  });
  return parseJson<{ success: boolean }>(res);
}

export async function reassembleProposal(
  docxFilename: string,
): Promise<{ success: boolean; docx_filename: string }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/proposal-sections/reassemble`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ docx_filename: docxFilename }),
  });
  return parseJson<{ success: boolean; docx_filename: string }>(res);
}

export async function getCompanyDBProfile(companyId: string = '_default'): Promise<{
  profile: {
    company_name: string;
    track_record_count: number;
    personnel_count: number;
  } | null;
}> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/profile?company_id=${encodeURIComponent(companyId)}`);
  return parseJson<{
    profile: {
      company_name: string;
      track_record_count: number;
      personnel_count: number;
    } | null;
  }>(res);
}

export async function updateCompanyDBProfile(
  data: { company_name: string },
  companyId: string = '_default',
  sessionId: string = '',
): Promise<{ success: boolean }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/company-db/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...data, company_id: companyId, session_id: sessionId }),
  });
  return parseJson<{ success: boolean }>(res);
}

// ── Pending Knowledge (학습 제안) ──

export async function getPendingKnowledge(
  companyId: string,
  docType: string = 'proposal',
): Promise<{ patterns: import('../types').LearnedPattern[] }> {
  const url = `${API_BASE_URL}/api/pending-knowledge?company_id=${encodeURIComponent(companyId)}&doc_type=${encodeURIComponent(docType)}`;
  const res = await fetchWithError(url);
  return parseJson<{ patterns: import('../types').LearnedPattern[] }>(res);
}

export async function approveKnowledge(
  companyId: string,
  patternKey: string,
  docType: string = 'proposal',
): Promise<{ success: boolean; message: string }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/approve-knowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_id: companyId, pattern_key: patternKey, doc_type: docType }),
  });
  return parseJson<{ success: boolean; message: string }>(res);
}

export async function rejectKnowledge(
  companyId: string,
  patternKey: string,
  docType: string = 'proposal',
): Promise<{ success: boolean; message: string }> {
  const res = await fetchWithError(`${API_BASE_URL}/api/reject-knowledge`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_id: companyId, pattern_key: patternKey, doc_type: docType }),
  });
  return parseJson<{ success: boolean; message: string }>(res);
}
