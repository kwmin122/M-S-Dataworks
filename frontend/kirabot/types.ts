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
  document_type: string;
  is_rfx_like: boolean;
}

export interface AnalyzeResponse {
  ok: boolean;
  filename: string;
  session_id: string;
  company_chunks: number;
  analysis: AnalysisPayload;
  matching: MatchingPayload;
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
