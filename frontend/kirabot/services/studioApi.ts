/**
 * Studio API client — project CRUD and stage management.
 */

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && window.location.port === '5173'
    ? 'http://localhost:8000'
    : '');

async function studioFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    let userMessage = `오류 ${res.status}`;
    try {
      const json = JSON.parse(body);
      if (json.detail) userMessage = json.detail;
    } catch { /* non-JSON body */ }
    throw new Error(userMessage);
  }
  return res.json();
}

// --- Types ---

export interface StudioProject {
  id: string;
  title: string;
  status: string;
  project_type: string;
  studio_stage: string | null;
  pinned_style_skill_id: string | null;
  active_analysis_snapshot_id: string | null;
  rfp_source_type: string | null;
  rfp_source_ref: string | null;
  settings_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export type StudioStage =
  | 'rfp'
  | 'package'
  | 'company'
  | 'style'
  | 'generate'
  | 'review'
  | 'relearn';

export const STUDIO_STAGES: { key: StudioStage; label: string }[] = [
  { key: 'rfp', label: '공고' },
  { key: 'package', label: '제출 패키지' },
  { key: 'company', label: '회사 역량' },
  { key: 'style', label: '스타일 학습' },
  { key: 'generate', label: '생성' },
  { key: 'review', label: '검토/보완' },
  { key: 'relearn', label: '재학습' },
];

// --- API functions ---

export type RfpSourceType = 'upload' | 'nara_search' | 'manual';

// --- Feature flags ---
/** Studio 자체 노출 여부 (Navbar, ProductHub) */
export function isStudioVisible(): boolean {
  return import.meta.env.VITE_STUDIO_VISIBLE !== 'false'; // default: true
}
/** Chat 생성 CTA를 Studio handoff로 전환 여부 */
export function isChatGenerationCutover(): boolean {
  return import.meta.env.VITE_CHAT_GENERATION_CUTOVER === 'true'; // default: false
}

// --- Chat handoff ---
export async function handoffFromChat(params: {
  title: string;
  analysis_json: Record<string, unknown>;
  summary_md?: string;
  go_nogo_result_json?: Record<string, unknown> | null;
}): Promise<StudioProject> {
  return studioFetch('/api/studio/handoff-from-chat', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function createStudioProject(params: {
  title: string;
  from_analysis_snapshot_id?: string;
  rfp_source_type?: RfpSourceType;
  rfp_source_ref?: string;
}): Promise<StudioProject> {
  return studioFetch('/api/studio/projects', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function listStudioProjects(): Promise<StudioProject[]> {
  return studioFetch('/api/studio/projects');
}

export async function getStudioProject(projectId: string): Promise<StudioProject> {
  return studioFetch(`/api/studio/projects/${projectId}`);
}

export async function updateStudioStage(
  projectId: string,
  stage: StudioStage,
): Promise<StudioProject> {
  return studioFetch(`/api/studio/projects/${projectId}/stage`, {
    method: 'PATCH',
    body: JSON.stringify({ studio_stage: stage }),
  });
}

// --- RFP Analysis ---

export interface AnalyzeResult {
  snapshot_id: string;
  version: number;
  title: string;
  summary_md: string;
  project: StudioProject;
}

export async function analyzeRfpText(
  projectId: string,
  documentText: string,
): Promise<AnalyzeResult> {
  return studioFetch(`/api/studio/projects/${projectId}/analyze`, {
    method: 'POST',
    body: JSON.stringify({ document_text: documentText }),
  });
}

export async function uploadAndAnalyzeRfp(
  projectId: string,
  file: File,
): Promise<AnalyzeResult & { filename: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(
    `${API_BASE}/api/studio/projects/${projectId}/upload-rfp`,
    {
      method: 'POST',
      credentials: 'include',
      body: formData,
      // No Content-Type header — browser sets multipart boundary
    },
  );
  if (!res.ok) {
    const body = await res.text();
    let msg = `오류 ${res.status}`;
    try { const j = JSON.parse(body); if (j.detail) msg = j.detail; } catch { /* */ }
    throw new Error(msg);
  }
  return res.json();
}

// --- Nara Search ---

export interface NaraBidNotice {
  id: string;
  title: string;
  issuingOrg: string;
  region: string | null;
  deadlineAt: string | null;
  estimatedPrice: string | null;
  category: string;
  awardMethod: string | null;
  url: string | null;
}

export interface NaraSearchResult {
  notices: NaraBidNotice[];
  total: number;
  page: number;
  pageSize: number;
}

export async function searchNaraBids(params: {
  keywords: string;
  category?: string;
  region?: string;
  period?: string;
  page?: number;
}): Promise<NaraSearchResult> {
  return studioFetch('/api/studio/search-bids', {
    method: 'POST',
    body: JSON.stringify({
      keywords: params.keywords,
      category: params.category || 'all',
      region: params.region || '',
      period: params.period || '1m',
      page: params.page || 1,
      page_size: 10,
    }),
  });
}

// --- Package classification ---

export interface PackageItem {
  id: string;
  package_category: 'generated_document' | 'evidence' | 'administrative' | 'price';
  document_code: string;
  document_label: string;
  required: boolean;
  status: string;
  generation_target: string | null;
  sort_order: number;
}

export interface ClassifyResult {
  procurement_domain: string;
  contract_method: string;
  confidence: number;
  detection_method: string;
  review_required?: boolean;
  matched_signals?: string[];
  warnings?: string[];
  package_items: PackageItem[];
}

export async function classifyPackage(projectId: string): Promise<ClassifyResult> {
  return studioFetch(`/api/studio/projects/${projectId}/classify`, {
    method: 'POST',
  });
}

export async function listPackageItems(projectId: string): Promise<PackageItem[]> {
  return studioFetch(`/api/studio/projects/${projectId}/package-items`);
}

export async function overridePackageClassification(
  projectId: string,
  params: {
    procurement_domain?: string;
    contract_method?: string;
    include_presentation?: boolean;
    add_items?: Array<{ document_label: string; package_category?: string; required?: boolean }>;
    remove_item_ids?: string[];
  },
): Promise<{ changes: Record<string, unknown>; package_items: PackageItem[] }> {
  return studioFetch(`/api/studio/projects/${projectId}/package-override`, {
    method: 'PATCH',
    body: JSON.stringify(params),
  });
}

// --- Company Assets ---

export type AssetCategory =
  | 'track_record'
  | 'personnel'
  | 'profile'
  | 'technology'
  | 'certification'
  | 'raw_document';

export interface CompanyAsset {
  id: string;
  asset_category: AssetCategory;
  label: string;
  content_json: Record<string, unknown>;
  promoted_at: string | null;
  promoted_to_id: string | null;
  created_at: string;
}

export interface MergedCompanyData {
  profile: Record<string, unknown> | null;
  track_records: Array<Record<string, unknown> & { source: 'shared' | 'staging' }>;
  personnel: Array<Record<string, unknown> & { source: 'shared' | 'staging' }>;
  other_assets: Array<Record<string, unknown> & { source: 'staging' }>;
}

export async function addCompanyAsset(
  projectId: string,
  params: { asset_category: AssetCategory; label: string; content_json: Record<string, unknown> },
): Promise<CompanyAsset> {
  return studioFetch(`/api/studio/projects/${projectId}/company-assets`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function listCompanyAssets(projectId: string): Promise<CompanyAsset[]> {
  return studioFetch(`/api/studio/projects/${projectId}/company-assets`);
}

export async function getCompanyMerged(projectId: string): Promise<MergedCompanyData> {
  return studioFetch(`/api/studio/projects/${projectId}/company-merged`);
}

export async function promoteCompanyAsset(
  projectId: string,
  assetId: string,
): Promise<{ promoted: boolean; promoted_to_id: string }> {
  return studioFetch(`/api/studio/projects/${projectId}/company-assets/${assetId}/promote`, {
    method: 'POST',
  });
}

// --- Style Skills ---

export interface StyleSkill {
  id: string;
  project_id: string | null;
  version: number;
  name: string;
  source_type: 'uploaded' | 'derived' | 'promoted';
  derived_from_id: string | null;
  profile_md_content: string | null;
  style_json: Record<string, unknown> | null;
  is_shared_default: boolean;
  created_at: string;
}

export async function createStyleSkill(
  projectId: string,
  params: {
    name: string;
    style_json?: Record<string, unknown>;
    profile_md_content?: string;
  },
): Promise<StyleSkill> {
  return studioFetch(`/api/studio/projects/${projectId}/style-skills`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function listStyleSkills(projectId: string): Promise<StyleSkill[]> {
  return studioFetch(`/api/studio/projects/${projectId}/style-skills`);
}

export async function pinStyleSkill(
  projectId: string,
  skillId: string,
): Promise<{ pinned_style_skill_id: string }> {
  return studioFetch(`/api/studio/projects/${projectId}/style-skills/${skillId}/pin`, {
    method: 'POST',
  });
}

export async function unpinStyleSkill(
  projectId: string,
): Promise<{ pinned_style_skill_id: null }> {
  return studioFetch(`/api/studio/projects/${projectId}/style-skills/pin`, {
    method: 'DELETE',
  });
}

export async function deriveStyleSkill(
  projectId: string,
  skillId: string,
  params: { name: string; style_json?: Record<string, unknown>; profile_md_content?: string },
): Promise<StyleSkill> {
  return studioFetch(`/api/studio/projects/${projectId}/style-skills/${skillId}/derive`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function promoteStyleSkill(
  projectId: string,
  skillId: string,
): Promise<{ promoted: boolean; shared_skill_id: string }> {
  return studioFetch(`/api/studio/projects/${projectId}/style-skills/${skillId}/promote`, {
    method: 'POST',
  });
}

// --- Proposal Generation ---

export interface GenerationContract {
  snapshot_id: string;
  snapshot_version: number;
  company_assets_count: number;
  company_context_length: number;
  pinned_style_skill_id: string | null;
  pinned_style_name: string | null;
  pinned_style_version: number | null;
  doc_type: string;
  total_pages: number;
  // PPT-specific
  proposal_revision_id?: string | null;
  execution_plan_revision_id?: string | null;
  target_slide_count?: number;
  duration_min?: number;
  qna_count?: number;
  available_inputs?: { proposal: boolean; execution_plan: boolean };
}

export interface GenerationPerformance {
  duration_sec: number;
  target_sec: number;
  within_target: boolean;
  timed_out: boolean;
  model: string | null;
}

export interface GenerateResult {
  run_id: string;
  revision_id: string;
  status: string;
  generation_contract: GenerationContract;
  sections_count: number;
  generation_time_sec: number | null;
  performance?: GenerationPerformance;
}

export type GenerateDocType = 'proposal' | 'execution_plan' | 'track_record' | 'presentation';

export async function generateProposal(
  projectId: string,
  params?: { doc_type?: GenerateDocType; total_pages?: number },
): Promise<GenerateResult> {
  return studioFetch(`/api/studio/projects/${projectId}/generate`, {
    method: 'POST',
    body: JSON.stringify(params ?? { doc_type: 'proposal' }),
  });
}

// --- Revision read ---

export interface RevisionSection {
  name: string;
  text: string;
}

export interface TrackRecordEntry {
  project_name: string;
  description: string;
  relevance_score?: number;
}

export interface PersonnelEntry {
  name: string;
  role: string;
  match_reason?: string;
}

export interface SlideMetadata {
  slide_type: string;
  title: string;
}

export interface QnaPairData {
  question: string;
  answer: string;
  category?: string;
}

export interface CurrentRevisionData {
  revision_id: string;
  revision_number: number;
  doc_type?: string;
  source: string;
  status: string;
  title: string | null;
  sections: RevisionSection[];
  records?: TrackRecordEntry[];
  personnel?: PersonnelEntry[];
  slides?: SlideMetadata[];
  qna_pairs?: QnaPairData[];
  slide_count?: number;
  total_duration_min?: number;
  quality_report: Record<string, unknown> | null;
  created_at: string | null;
}

export async function getCurrentRevision(
  projectId: string,
  docType: GenerateDocType,
): Promise<CurrentRevisionData> {
  return studioFetch(`/api/studio/projects/${projectId}/documents/${docType}/current`);
}

// --- Package item lifecycle ---

export interface PackageCompleteness {
  total: number;
  completed: number;
  waived: number;
  required_remaining: number;
  completeness_pct: number;
}

export async function getPackageCompleteness(projectId: string): Promise<PackageCompleteness> {
  return studioFetch(`/api/studio/projects/${projectId}/package-completeness`);
}

export async function updatePackageItemStatus(
  projectId: string,
  itemId: string,
  status: 'missing' | 'waived' | 'verified',
): Promise<{ id: string; status: string; document_code: string }> {
  return studioFetch(`/api/studio/projects/${projectId}/package-items/${itemId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export async function attachEvidenceFile(
  projectId: string,
  itemId: string,
  file: File,
): Promise<{ asset_id: string; status: string; document_code: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(
    `${API_BASE}/api/studio/projects/${projectId}/package-items/${itemId}/evidence`,
    {
      method: 'POST',
      credentials: 'include',
      body: formData,
      // No Content-Type header — browser sets multipart boundary
    },
  );
  if (!res.ok) {
    const body = await res.text();
    let msg = `오류 ${res.status}`;
    try { const j = JSON.parse(body); if (j.detail) msg = j.detail; } catch { /* */ }
    throw new Error(msg);
  }
  return res.json();
}

// --- Proposal review/relearn ---

export interface DiffSection {
  name: string;
  original: string;
  edited: string;
  changed: boolean;
}

export interface ProposalDiffResult {
  sections: DiffSection[];
  changed_sections_count: number;
  total_sections: number;
  edit_rate: number;
}

export interface RelearnResult {
  new_skill_id: string;
  new_skill_version: number;
  derived_from_id: string;
  edit_notes_count: number;
}

export async function saveEditedDocument(
  projectId: string,
  docType: GenerateDocType,
  sections: Array<{ name: string; text: string }>,
): Promise<{ revision_id: string; revision_number: number; source: string }> {
  return studioFetch(`/api/studio/projects/${projectId}/documents/${docType}/edited`, {
    method: 'POST',
    body: JSON.stringify({ sections }),
  });
}

export async function getDocumentDiff(
  projectId: string,
  docType: GenerateDocType,
): Promise<ProposalDiffResult> {
  return studioFetch(`/api/studio/projects/${projectId}/documents/${docType}/diff`);
}

export async function relearnDocumentStyle(
  projectId: string,
  docType: GenerateDocType = 'proposal',
): Promise<RelearnResult> {
  return studioFetch(`/api/studio/projects/${projectId}/relearn?doc_type=${docType}`, {
    method: 'POST',
  });
}

// Backward compatibility — keep existing function names
export const saveEditedProposal = (projectId: string, sections: Array<{ name: string; text: string }>) =>
  saveEditedDocument(projectId, 'proposal', sections);
export const getProposalDiff = (projectId: string) =>
  getDocumentDiff(projectId, 'proposal');
export const relearnProposalStyle = (projectId: string) =>
  relearnDocumentStyle(projectId, 'proposal');

// --- Admin Observability Metrics ---

export interface AdminMetricsSummary {
  total_events: number;
  success_count: number;
  failure_count: number;
  timeout_count: number;
  success_rate: number;
}

export interface EventTypeMetrics {
  count: number;
  success: number;
  failure: number;
  avg_duration_ms: number;
}

export interface DocTypeMetrics {
  count: number;
  avg_duration_ms: number;
}

export interface ModelCost {
  tokens: number;
  cost_usd: number;
}

export interface AdminMetrics {
  period_days: number;
  summary: AdminMetricsSummary;
  by_event_type: Record<string, EventTypeMetrics>;
  by_doc_type: Record<string, DocTypeMetrics>;
  cost: { total_usd: number; by_model: Record<string, ModelCost> };
  quality: { override_count: number; low_confidence_count: number; avg_quality_score: number | null };
  daily_trend: Array<{ date: string; events: number; success: number; failure: number }>;
}

export async function getAdminMetrics(days: number = 30): Promise<AdminMetrics> {
  return studioFetch(`/api/studio/admin/metrics?days=${days}`);
}
