export interface Message {
  id: string;
  role: 'user' | 'model';
  text: string;
  timestamp: number;
}

export interface UploadedDocument {
  id: string;
  name: string;
  type: string;
  size: number;
  content?: string; // Extracted text content for analysis
  uploadDate: Date;
}

export enum AppView {
  LANDING = 'LANDING',
  DASHBOARD = 'DASHBOARD',
  PRIVACY = 'PRIVACY',
  TERMS = 'TERMS',
}

export interface User {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
  isAdmin?: boolean;
}

export interface SessionStats {
  session_id: string;
  company_chunks: number;
  created_at: string;
  last_used_at: string;
}

export interface RequirementMatch {
  category: string;
  description: string;
  is_mandatory: boolean;
  status: string;
  status_code: 'MET' | 'PARTIALLY_MET' | 'NOT_MET' | 'UNKNOWN';
  confidence: number;
  evidence: string;
  preparation_guide: string;
  source_files: string[];
}

export interface MatchingPayload {
  overall_score: number;
  recommendation: string;
  summary: string;
  met_count: number;
  partially_met_count: number;
  not_met_count: number;
  unknown_count: number;
  matches: RequirementMatch[];
  assistant_opinions: Record<string, {
    opinion: string;
    actions: string[];
    risk_notes: string[];
    generated_at?: string;
  }>;
}

export interface AnalysisPayload {
  title: string;
  issuing_org: string;
  announcement_number?: string;
  deadline?: string;
  project_period?: string;
  budget?: string;
  document_type: string;
  is_rfx_like: boolean;
  document_gate_reason?: string;
  document_gate_confidence?: number;
  requirements: {
    category: string;
    description: string;
    is_mandatory: boolean;
    detail?: string;
  }[];
  evaluation_criteria?: {
    category: string;
    item: string;
    score: number;
    detail?: string;
  }[];
  required_documents?: string[];
  special_notes?: string[];
  rfp_summary?: string;
}

export interface AnalyzeResponse {
  ok: boolean;
  filename: string;
  session_id: string;
  company_chunks: number;
  analysis: AnalysisPayload;
  matching: MatchingPayload | null;
  fileUrl?: string;
}

export interface ChatReference {
  page: number;
  text: string;
}

export interface ChatResponse {
  ok: boolean;
  blocked: boolean;
  policy: string;
  intent: string;
  reason: string;
  answer: string;
  references: ChatReference[];
  suggested_questions: string[];
}

// ── SaaS API 응답 타입 ──

export interface BidNotice {
  id: string;               // bid_ntce_no
  title: string;            // bid_ntce_nm
  issuingOrg?: string;      // ntce_instt_nm
  demandOrg?: string;       // dminstt_nm
  region: string | null;
  deadlineAt: string | null;
  url: string | null;
  estimatedPrice?: string;
  category?: string;        // 물품/용역/공사/외자/기타
  bidNtceOrd?: string;      // 입찰공고차수
}

export interface BidSearchResponse {
  notices: BidNotice[];
  total: number;
  page: number;
  pageSize: number;
}

export interface NaraAttachment {
  fileNm: string;
  fileUrl: string;
  fileSize: number;
}

export interface EvalJob {
  id: string;
  bidNoticeId: string;
  isEligible: boolean | null;
  evaluationReason: string;
  actionPlan: string | null;
  bidNotice: BidNotice;
}

export interface EvalBatchResponse {
  jobsCreated: number;
  jobs: EvalJob[];
}

export interface ProposalSections {
  [key: string]: string;
}

export interface SearchConditions {
  keywords: string[];
  region: string;
  minAmt: string;
  maxAmt: string;
  period: '1w' | '1m' | '3m';
  excludeExpired: boolean;
  includeAttachmentText: boolean;
}

// ── 대화형 UI 메시지 타입 ──

export type ChatMessageType =
  | 'text'
  | 'button_choice'
  | 'bid_card_list'
  | 'analysis_result'
  | 'inline_form'
  | 'file_upload'
  | 'status'
  | 'checklist'
  | 'learning_suggestion';

export interface BaseChatMessage {
  id: string;
  role: 'user' | 'bot';
  type: ChatMessageType;
  timestamp: number;
}

export interface TextChatMessage extends BaseChatMessage {
  type: 'text';
  text: string;
  references?: ChatReference[];
  scoped_to?: string[];
}

export interface ButtonChoiceMessage extends BaseChatMessage {
  type: 'button_choice';
  text: string;
  choices: { label: string; value: string }[];
  selectedValue?: string;
}

export interface BidCardListMessage extends BaseChatMessage {
  type: 'bid_card_list';
  text: string;
  cards: BidNotice[];
  selectedIds?: string[];
  total?: number;
  page?: number;
  pageSize?: number;
  searchConditions?: Record<string, string>;
}

export interface AnalysisResultMessage extends BaseChatMessage {
  type: 'analysis_result';
  analysis: AnalyzeResponse;
  opinionMode: OpinionMode;
}

export interface InlineFormMessage extends BaseChatMessage {
  type: 'inline_form';
  text: string;
  fields: {
    key: string;
    label: string;
    type: 'text' | 'number' | 'select' | 'multiselect';
    options?: string[];
  }[];
  submitLabel: string;
  submittedValues?: Record<string, string>;
}

export interface FileUploadMessage extends BaseChatMessage {
  type: 'file_upload';
  text: string;
  accept: string;
  multiple: boolean;
  uploadedFileNames?: string[];
}

export interface StatusChatMessage extends BaseChatMessage {
  type: 'status';
  text: string;
  level: 'loading' | 'success' | 'error' | 'info';
  retryAction?: string;
}

export interface ChecklistItem {
  document_name: string;
  is_mandatory: boolean;
  format_hint: string;
  deadline_note: string;
  status: string;
}

export interface ChecklistChatMessage extends BaseChatMessage {
  type: 'checklist';
  items: ChecklistItem[];
  total: number;
  mandatory_count: number;
}

export interface LearnedPattern {
  pattern_key: string;
  diff_type: string;
  section_name: string;
  original_example: string;
  edited_example: string;
  occurrence_count: number;
  description: string;
  status: 'pending' | 'confirmed';
}

export interface LearningSuggestionMessage extends BaseChatMessage {
  type: 'learning_suggestion';
  text: string;
  patterns: LearnedPattern[];
  doc_type: string;
}

export type ChatMessage =
  | TextChatMessage
  | ButtonChoiceMessage
  | BidCardListMessage
  | AnalysisResultMessage
  | InlineFormMessage
  | FileUploadMessage
  | StatusChatMessage
  | ChecklistChatMessage
  | LearningSuggestionMessage;

// ── 대화 Phase ──

export type ConversationPhase =
  | 'greeting'
  | 'doc_upload_company'
  | 'doc_upload_target'
  | 'doc_analyzing'
  | 'doc_chat'
  | 'bid_search_input'
  | 'bid_search_results'
  | 'bid_analyzing'
  | 'bid_eval_running'
  | 'bid_eval_results'
  | 'free_chat';

export type OpinionMode = 'conservative' | 'balanced' | 'aggressive';

// ── 대화 ──

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  phase: ConversationPhase;
  sessionId?: string;
  companyChunks?: number;
  opinionMode: OpinionMode;
  selectedBidIds?: string[];
  uploadedFileUrl?: string;
  uploadedFileName?: string;
  companyDocUrls?: { name: string; url: string }[];
  companyDocuments?: CompanyDocInfo[];
  _justUploadedFiles?: string[];
  companyProfile?: CompanyProfile | null;
  activeDocFilter?: string[] | null;
  _onboardingStep?: 'basic_info' | 'track_records' | 'personnel';
}

// ── 컨텍스트 패널 ──

export type DocFileType = 'pdf' | 'excel' | 'hwp' | 'docx' | 'ppt' | 'other';

export interface DocumentTab {
  label: string;
  url: string;
  fileName: string;
  fileType: DocFileType;
  page?: number;
  highlightText?: string;
}

export type ContextPanelContent =
  | { type: 'none' }
  | { type: 'pdf'; blobUrl: string; page?: number; highlightText?: string }
  | { type: 'documents'; tabs: DocumentTab[]; activeTabIndex: number }
  | { type: 'bid_detail'; bid: BidNotice }
  | { type: 'proposal'; sections: ProposalSections; bidNoticeId: string };

// ── 메시지 액션 ──

export type MessageAction =
  | { type: 'choice_selected'; value: string; messageId: string }
  | { type: 'bid_selected'; bidIds: string[]; messageId: string }
  | { type: 'form_submitted'; values: Record<string, string>; messageId: string }
  | { type: 'files_uploaded'; files: File[]; messageId: string }
  | { type: 'reference_clicked'; page: number; text?: string }
  | { type: 'retry_action'; action: string }
  | { type: 'analyze_bid'; bid: BidNotice; messageId: string }
  | { type: 'search_page'; page: number; conditions: Record<string, string>; messageId: string }
  | { type: 'header_upload_target' }
  | { type: 'header_add_company' }
  | { type: 'setup_alert' }
  | { type: 'welcome_action'; value: string }
  | { type: 'generate_proposal_v2'; bidTitle: string }
  | { type: 'delete_company_doc'; sourceFile: string }
  | { type: 'undo_company_upload'; sourceFiles: string[] }
  | { type: 'ask_about_doc'; sourceFile: string }
  | { type: 'view_checklist' }
  | { type: 'generate_wbs' }
  | { type: 'generate_ppt' }
  | { type: 'generate_track_record' }
  | { type: 'open_company_onboarding' }
  | { type: 'open_pending_knowledge' };

// ── 문서 멘션 (다중 문서 질의) ──

export interface DocMention {
  sourceFile: string;
  label: string;
  type: 'company' | 'rfx';
}

// ── 세션 기반 회사 문서 (벡터 DB) ──

export interface CompanyDocInfo {
  source_file: string;
  chunks: number;
  url: string;
}

// ── 회사 프로필 ──

export interface CompanyDocument {
  id: string;
  name: string;
  uploadedAt: string;
  size: number;
}

export interface AiExtraction {
  summary: string;
  extractedAt: string;
  raw: Record<string, unknown>;
}

export interface CompanyProfile {
  companyName: string;
  businessType: string;
  businessNumber: string;
  certifications: string[];
  regions: string[];
  employeeCount: number | null;
  annualRevenue: string;
  keyExperience: string[];
  specializations: string[];
  documents: CompanyDocument[];
  aiExtraction: AiExtraction | null;
  lastAnalyzedAt: string | null;
  createdAt: string;
  updatedAt?: string;
}

// ── Document Workspace ──

export interface ProfileSection {
  name: string;
  content: string;
  editable: boolean;
}

export interface ProfileMdResponse {
  sections: ProfileSection[];
  metadata: { version: number; company_id: string };
}

export interface ProfileVersion {
  version: number;
  date: string;
  reason: string;
}

export interface ProfileHistoryResponse {
  versions: ProfileVersion[];
  current_version: number;
}

// ── Proposal Sections (DocumentWorkspace) ──

export interface ProposalSectionData {
  name: string;
  text: string;
}

export interface ProposalSectionsResponse {
  title: string;
  sections: ProposalSectionData[];
}

// ── Payment / Subscription ──
export interface Subscription {
  username?: string;
  plan: 'free' | 'pro';
  status: 'none' | 'active' | 'cancelled';
  cardLast4?: string;
  priceKrw?: number;
  createdAt?: string;
  currentPeriodStart?: string;
  currentPeriodEnd?: string;
  cancelledAt?: string;
  updatedAt?: string;
}

// ── Company Onboarding ──
export interface TrackRecordInput {
  project_name: string;
  client: string;
  period: string;
  contract_amount?: string;
  description?: string;
  technologies?: string[];
}

export interface PersonnelInput {
  name: string;
  role: string;
  experience_years: number;
  certifications?: string[];
  description?: string;
}

export interface CompanyOnboardingData {
  companyName: string;
  trackRecord: TrackRecordInput | null;
  personnel: PersonnelInput | null;
}
