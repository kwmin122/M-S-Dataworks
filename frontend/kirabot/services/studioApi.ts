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
}

export interface GenerateResult {
  run_id: string;
  revision_id: string;
  status: string;
  generation_contract: GenerationContract;
  sections_count: number;
  generation_time_sec: number | null;
}

export async function generateProposal(
  projectId: string,
  params?: { doc_type?: 'proposal'; total_pages?: number },
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

export interface CurrentRevisionData {
  revision_id: string;
  revision_number: number;
  source: string;
  status: string;
  title: string | null;
  sections: RevisionSection[];
  quality_report: Record<string, unknown> | null;
  created_at: string | null;
}

export async function getCurrentRevision(
  projectId: string,
  docType: string,
): Promise<CurrentRevisionData> {
  return studioFetch(`/api/studio/projects/${projectId}/documents/${docType}/current`);
}
