export type ProcessingStatus =
  | "queued"
  | "parsing"
  | "chunking"
  | "embedding"
  | "complete"
  | "failed";

export interface DocumentSummary {
  id: string;
  filename: string;
  source_type: string;
  mime_type: string;
  file_size_bytes: number | null;
  processing_status: ProcessingStatus;
  error_message: string | null;
  word_count: number | null;
  chunk_count: number | null;
  language: string | null;
  uploaded_at: string;
  completed_at: string | null;
  credibility_score?: number | null;
  credibility_breakdown?: Record<string, unknown> | null;
  credibility_computed_at?: string | null;
  source_url?: string | null;
}

export interface DocumentStatus {
  document_id: string;
  processing_status: ProcessingStatus;
  error_message: string | null;
  chunk_count: number | null;
  completed_at: string | null;
}

// ----- Phase 3.5: annotations -----

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  text: string;
  page_number: number | null;
  section: string | null;
}

export type AnnotationColor = "yellow" | "green" | "blue" | "pink" | "purple";

export interface Annotation {
  id: string;
  document_id: string;
  document_filename: string;
  chunk_id: string | null;
  insight_entity_id: string | null;
  highlight_text: string;
  char_start: number | null;
  char_end: number | null;
  note: string | null;
  tags: string[];
  color: AnnotationColor;
  created_at: string;
  updated_at: string;
}

// ----- Phase 3.6: spaced repetition -----

export interface Flashcard {
  id: string;
  document_id: string | null;
  chunk_id: string | null;
  question: string;
  answer: string;
  reps: number;
  interval_days: number;
  ease: number;
  due_date: string;
  suspended: boolean;
  created_at: string;
}

export interface CardStats {
  total: number;
  due_today: number;
  mastered: number;
  suspended: number;
  reviews_last_7_days: number;
  streak_days: number;
}

export interface ReviewResult {
  id: string;
  reps: number;
  interval_days: number;
  ease: number;
  due_date: string;
}

export interface Citation {
  index: number;
  chunk_id: string;
  document_title: string;
  page_number: number | null;
  section: string | null;
  snippet: string;
}

export interface QAResponse {
  answer: string;
  citations: Citation[];
  confidence_score: number;
  no_source_found: boolean;
  conversation_id: string | null;
}

export interface IngestResponse {
  document_id: string;
  filename: string;
  processing_status: ProcessingStatus;
}

// ----- Phase 2: knowledge graph -----

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  evidence_count: number;
}

export interface GraphEdge {
  id: string;
  src: string;
  dst: string;
  relation: string;
  confidence: number;
}

export interface GraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface EntityChunkEvidence {
  chunk_id: string;
  document_id: string;
  page: number | null;
  snippet: string;
}

export interface EntityNeighbor {
  entity_id: string;
  name: string;
  type: string;
  relation: string;
  confidence: number;
  direction: "in" | "out";
}

export interface EntityDetail {
  id: string;
  name: string;
  canonical_name: string;
  type: string;
  evidence_count: number;
  aliases: string[];
  evidence: EntityChunkEvidence[];
  neighbors: EntityNeighbor[];
}

export interface EdgeDetail {
  id: string;
  src_id: string;
  dst_id: string;
  src_name: string;
  dst_name: string;
  relation: string;
  confidence: number;
  evidence_chunk_id: string;
  evidence_document_id: string;
  evidence_page: number | null;
  evidence_snippet: string;
  justification: string;
}

// ----- Phase 2.5: claims & contradictions -----

export interface ClaimItem {
  id: string;
  document_id: string;
  chunk_id: string;
  claim_text: string;
  polarity: "affirm" | "negate";
  llm_confidence: number;
  created_at: string;
}

export interface ConflictItem {
  id: string;
  claim_a: ClaimItem;
  claim_b: ClaimItem;
  embedding_similarity: number;
  nli_contradiction_score: number;
  status: "auto" | "confirmed" | "dismissed";
  created_at: string;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
}

// ----- Phase 2.5: credibility -----

export interface CredibilityBreakdownSignal {
  value: number;
  weight: number;
  [key: string]: unknown;
}

export interface CredibilityBreakdown {
  recency: CredibilityBreakdownSignal & { age_days: number; half_life_days: number };
  source_type: CredibilityBreakdownSignal & { label: string };
  cross_source_agreement: CredibilityBreakdownSignal & { corroborating_claim_count: number };
  citation_density: CredibilityBreakdownSignal & { shared_entities: number; total_entities: number };
  weights_version: string;
  score: number;
}

export interface CredibilityInfo {
  document_id: string;
  score: number | null;
  label: "low" | "moderate" | "high" | "very_high" | null;
  breakdown: CredibilityBreakdown | null;
  computed_at: string | null;
}

// ----- Phase 2: document intelligence -----

export interface IntelligenceMetrics {
  flesch_kincaid_grade: number;
  reading_minutes: number;
  jargon_density: number;
}

export interface KeyInsight {
  claim: string;
  source_chunk_id: string;
  confidence: number;
}

export interface DocumentIntelligence {
  abstract: string;
  summary: string[];
  deep_dive: string;
  key_insights: KeyInsight[];
  tags: string[];
  metrics: IntelligenceMetrics | null;
  computed_at: string | null;
}
