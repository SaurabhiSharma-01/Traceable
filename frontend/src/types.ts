/**
 * types.ts — TypeScript mirror of backend/app/models.py (Pydantic v2).
 *
 * SPEC rule: change backend/app/models.py and this file together.
 * Nullable Pydantic fields (Optional[X]) map to `X | null` here.
 */

// ---------------------------------------------------------------------------
// Core pipeline types
// ---------------------------------------------------------------------------

export interface Passage {
  id: string;          // e.g. "S2-P5"
  source_id: string;
  text: string;
  order: number;
}

export type SourceType = 'url' | 'text' | 'pdf' | 'search';
export type SourceClass = 'official' | 'news' | 'aggregator' | 'blog' | 'forum' | 'unknown';
export type DateOrigin = 'meta' | 'jsonld' | 'visible_text' | 'url_pattern' | 'none';
export type DateStatus = 'fresh' | 'stale' | 'undated';
export type FetchStatus = 'ok' | 'failed' | 'blocked' | 'empty';

export interface Source {
  id: string;
  type: SourceType;
  url: string | null;
  title: string | null;
  domain: string | null;
  source_class: SourceClass;
  fetched_at: string;            // ISO datetime string
  published_date: string | null; // ISO datetime string
  date_origin: DateOrigin;
  date_status: DateStatus;
  cycle_year: number | null;
  fetch_status: FetchStatus;
  error_message: string | null;
  passages: Passage[];
}

export interface ExpectedTopic {
  key: string;          // e.g. "eligibility_criteria"
  label: string;        // Human-readable, e.g. "Eligibility Criteria"
  importance: number;   // 1–5
  description: string;
}

export type Confidence = 'low' | 'medium' | 'high';

export interface Fact {
  source_id: string;
  topic_key: string;
  found: boolean;
  value: string | null;
  quote: string | null;
  passage_id: string | null;
  cycle_year: number | null;
  confidence: Confidence;
  quote_verified: boolean;
}

export interface EvidenceRef {
  source_id: string;
  passage_id: string | null;
  quote: string | null;
}

export type FindingKind = 'summary' | 'gap' | 'conflict' | 'stale' | 'unanswered_question' | 'risk';
export type FindingLabel = 'SOURCED' | 'POTENTIAL' | 'UNCERTAIN';
export type EvidenceLevel =
  | 'primary_supported'
  | 'corroborated'
  | 'single_origin'
  | 'contradicted_by_primary'
  | 'unsupported';

export interface Finding {
  id: string;
  kind: FindingKind;
  label: FindingLabel;
  topic_key: string | null;
  title: string;
  explanation: string;
  evidence: EvidenceRef[];
  confidence: Confidence | null;
  evidence_level: EvidenceLevel | null;
  independent_origins: number | null;
  priority_score: number;
}

export interface ChecklistItem {
  id: string;
  priority_rank: number;
  action: string;
  reason: string;
  linked_finding_ids: string[];
  suggested_official_source: string | null;
  status: 'todo' | 'done';
}

export interface Analysis {
  id: string;
  question: string;
  entity: string | null;
  expected_topics: ExpectedTopic[];
  sources: Source[];
  facts: Fact[];
  coverage_matrix: Record<string, Record<string, boolean>>;
  findings: Finding[];
  checklist: ChecklistItem[];
  warnings: string[];
  created_at: string; // ISO datetime string
}

// ---------------------------------------------------------------------------
// API request / response types
// ---------------------------------------------------------------------------

export interface UnderstandRequest {
  question: string;
}

export interface UnderstandResponse {
  entity: string;
  expected_topics: ExpectedTopic[];
}

export interface SearchSourcesRequest {
  entity: string;
  topics: ExpectedTopic[];
  max_results?: number;
}

/** Candidate source returned by the search endpoint (not yet fetched/cleaned). */
export interface CandidateSource {
  url: string;
  title: string;
  snippet: string;
}

export interface FetchSourcesRequest {
  urls: string[];
  pasted_texts: string[];
}

export interface StartAnalysisRequest {
  question: string;
  entity: string;
  expected_topics: ExpectedTopic[];
  source_ids: string[];
}

export interface ProgressEvent {
  stage: string;
  message: string;
  percent: number;
}

