/**
 * Frontend-facing domain types.
 *
 * These describe the shapes the UI renders. They are intentionally decoupled
 * from any backend contract — the data layer in `src/lib/api.ts` is the single
 * integration point where real API responses get mapped onto these types.
 */

export type RiskLevel = "low" | "medium" | "high";

export type DocumentStatus =
  | "uploading"
  | "processing"
  | "extracting"
  | "analyzing"
  | "completed"
  | "failed";

export type DocumentType =
  | "Lab Report"
  | "Prescription"
  | "Discharge Summary"
  | "Imaging Report"
  | "Doctor Note";

export interface MedicalDocument {
  id: string;
  title: string;
  type: DocumentType;
  provider: string;
  documentDate: string;
  uploadedAt: string;
  processedAt?: string;
  pages: number;
  sizeLabel: string;
  status: DocumentStatus;
  source: "digital" | "scanned";
  extractedItems?: number;
}

export interface DocumentDetail extends MedicalDocument {
  extractedText?: string;
  extractionMethod?: string;
  pageCount?: number;
  medications: Medication[];
  findings: Finding[];
  labResults: LabResult[];
  allergies: AllergyRecord[];
  events: TimelineEvent[];
  aiSummary?: string;
  aiConfidence?: number;
}

export type PipelineStepStatus = "done" | "active" | "pending" | "failed";

export interface PipelineStep {
  id: string;
  title: string;
  description: string;
  status: PipelineStepStatus;
  detail?: string;
}

export interface UploadItem {
  id: string;
  fileName: string;
  sizeLabel: string;
  progress: number;
  status: DocumentStatus;
  message?: string;
}

export type TimelineEventKind =
  | "lab"
  | "prescription"
  | "visit"
  | "imaging"
  | "note";

export interface TimelineEvent {
  id: string;
  date: string;
  kind: TimelineEventKind;
  title: string;
  provider: string;
  summary: string;
  documentTitle: string;
  documentId: string;
  tags: string[];
  risk?: RiskLevel;
}

export interface Medication {
  id: string;
  name: string;
  genericName: string;
  dosage: string;
  frequency: string;
  startedOn: string;
  prescribedBy: string;
  sourceDocumentId: string;
  sourceDocumentName?: string;
  instructions?: string;
  status: "active" | "stopped";
  flags: MedicationFlagKind[];
}

export interface MedicalOverview {
  patientId: string;
  totalDocuments: number;
  totalMedications: number;
  totalFindings: number;
  totalEvents: number;
  totalLabResults: number;
  totalAllergies: number;
  latestSummary?: string;
  confidenceScore?: number;
  recentEvents: TimelineEvent[];
  activeMedications: Medication[];
  priorityFindings: Finding[];
}

export interface AllergyRecord {
  id: string;
  medicationName: string;
  normalizedMedicationName: string;
  reaction?: string;
  severity?: "mild" | "moderate" | "severe" | string;
  sourceDocumentId?: string;
  sourceDocumentName?: string;
  recordedDate: string;
  createdAt: string;
}

export interface DocumentExtractionCounts {
  events?: number;
  medications?: number;
  prescriptions?: number;
  lab_results?: number;
  allergies?: number;
  findings?: number;
  ai_analyses?: number;
}

export interface DocumentExtractionResultPayload {
  summary?: string | null;
  document_type_detected?: string | null;
  confidence_score?: number | null;
  persisted_counts?: DocumentExtractionCounts;
}

export interface QAResultPayload {
  paragraphs?: string[];
  citations?: ChatCitation[];
  confidence?: number | null;
  guidance?: string | null;
  refusal?: {
    overline?: string;
    headline?: string;
    suggestions?: string[];
    footnote?: string;
  } | null;
  cta?: {
    label?: string;
    note?: string;
  } | null;
}

export interface AIAnalysisRecord {
  id: string;
  analysisType: string;
  result: Record<string, unknown> | DocumentExtractionResultPayload | QAResultPayload;
  confidence?: number;
  relatedFindingId?: string;
  relatedFindingTitle?: string;
  summary?: string;
  createdAt: string;
}

export type MedicationFlagKind =
  | "interaction"
  | "duplicate"
  | "dosage"
  | "allergy";

export interface CrossCheckIssue {
  id: string;
  kind: MedicationFlagKind;
  risk: RiskLevel;
  title: string;
  medications: string[];
  explanation: string;
  recommendation: string;
  confidence: number;
}

/**
 * Result of the deterministic medication safety check.
 *
 * Each detected issue is a `CrossCheckIssue`, so the medications screen renders
 * safety data from the engine with no separate shape of its own.
 */
export interface MedicationSafetyReport {
  /** Date the engine used to decide which prescriptions count as active. */
  referenceDate: string;
  activeMedicationCount: number;
  /** Normalized generic names of the medications that were analysed. */
  activeMedications: string[];
  findingCount: number;
  /** Highest risk present, or null when no issues were detected. */
  highestRiskLevel: RiskLevel | null;
  issues: CrossCheckIssue[];
}

/**
 * Backend classification of one value against its reference range
 * (`LabResultAnalysisResponse.status`).
 *
 * UNKNOWN is a real, distinct state — the value or the range could not be read
 * unambiguously. It must never be rendered as NORMAL, "OK" or 0.
 */
export type LabStatus = "NORMAL" | "HIGH" | "LOW" | "UNKNOWN";

/**
 * Backend historical direction for a test (`LabTrendResponse.trend`).
 *
 * INSUFFICIENT_DATA means fewer than two numeric points exist, which is not the
 * same claim as STABLE and must never be displayed as it.
 */
export type LabTrendDirection =
  | "INCREASING"
  | "DECREASING"
  | "STABLE"
  | "INSUFFICIENT_DATA";

export interface LabResult {
  id: string;
  name: string;
  unit: string;
  referenceRange: string;
  referenceLow?: number;
  referenceHigh?: number;
  /**
   * The exact number the laboratory reported, or null when the value is
   * censored ("<0.01"), locale-ambiguous ("1,200") or otherwise unreadable.
   * Never substitute 0 — that is a measurement the lab did not make.
   */
  latestValue: number | null;
  /** Exactly what the lab reported, preserving "<0.01" and trailing zeros. */
  latestValueLabel: string;
  latestDate: string;
  sourceDocument: string;
  sourceDocumentId: string | null;
  trend: LabTrendDirection;
  status: LabStatus;
  points: LabTrendPoint[];
}

/**
 * Legacy Figma point type, consumed only by the pre-existing `Sparkline` and
 * `LabTrendChart` components. Left exactly as-is so those components keep their
 * current API; lab intelligence uses `LabTrendPoint` instead.
 */
export interface LabPoint {
  date: string;
  value: number;
  documentId: string;
}

/**
 * One historical point from /api/lab-intelligence, mapped from
 * `LabTrendPointResponse`.
 *
 * Distinct from `LabPoint` because a laboratory point legitimately has no exact
 * number: a censored "<0.01" or an ambiguous "1,200" carries `value: null`.
 * Substituting 0 would assert a measurement the laboratory never made.
 */
export interface LabTrendPoint {
  date: string;
  /** null when this point carries no exact number. Never rendered as 0. */
  value: number | null;
  /** Exactly what the lab reported for this point, e.g. "<0.01". */
  valueLabel: string;
  status: LabStatus;
  documentId: string | null;
  documentName: string | null;
}

/** GET /api/lab-intelligence/trends/{test_name} */
export interface LabTrend {
  testName: string;
  unit: string | null;
  trend: LabTrendDirection;
  points: LabTrendPoint[];
}

/** GET /api/lab-intelligence/overview */
export interface LabIntelligenceOverview {
  results: LabResult[];
  availableTests: string[];
}

export interface EvidenceReference {
  id: string;
  documentId: string;
  documentTitle: string;
  page: number;
  quote: string;
  /** e.g. "12 Mar 2026 · Lakeside Clinic" */
  recordedOn: string;
  /** Colour of the quote's left rule in the finding detail view. */
  tone?: RiskLevel;
}

export interface DeterminationStep {
  kind: "deterministic" | "ai";
  text: string;
}

export interface Finding {
  id: string;
  title: string;
  category: MedicationFlagKind | "lab-trend" | "follow-up";
  /** Overline chip on the finding card, e.g. "ALLERGY CHECK". */
  categoryLabel: string;
  /** Long form used in the detail hero, e.g. "Allergy / contradiction". */
  categoryName: string;
  risk: RiskLevel;
  confidence: number;
  summary: string;
  detectedOn: string;
  detectedAt: string;
  documentsInvolved: string;
  reviewStatus: string;
  /** e.g. "Prompt consultation recommended". */
  guidance: string;
  relatedMedications: string[];
  evidence: EvidenceReference[];
  whatThisMeans: string;
  determination: DeterminationStep[];
  contributingFactors: string[];
  recommendedAction: string;
  suitableProfessional: { title: string; rationale: string };
  providerCta: { label: string; primary: boolean };
}

export interface ChatCitation {
  documentId: string;
  documentTitle: string;
  page: number;
  quote: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  /** One entry per rendered paragraph. */
  paragraphs: string[];
  citations?: ChatCitation[];
  confidence?: number;
  /** e.g. "Consider consulting a qualified healthcare professional". */
  guidance?: string;
  /** Present when the assistant declines to answer for medical-safety reasons. */
  refusal?: {
    overline: string;
    headline: string;
    suggestions: string[];
    footnote: string;
  };
  /** Provider hand-off shown under high-risk answers. */
  cta?: { label: string; note: string };
}

export type ProviderKind =
  | "hospital"
  | "clinic"
  | "doctor"
  | "pharmacy"
  | "laboratory";

/**
 * One healthcare provider returned by the backend.
 *
 * Every nullable field is null when OpenStreetMap published nothing for it.
 * Null means "not published" and is rendered as "Not available" — it is never
 * substituted with a plausible-looking value.
 */
export interface Provider {
  id: string;
  name: string;
  /** Empty string only if a stored record carries a scope this build cannot read. */
  kind: ProviderKind | "";
  /** Empty when the source published no specialty; never inferred from `kind`. */
  specialties: string[];
  address: string | null;
  /** Straight-line distance; null when either side lacks coordinates. */
  distanceKm: number | null;
  /** Published opening hours, verbatim. Never an appointment time. */
  openingHours: string | null;
  phone: string | null;
  website: string | null;
  /** 0–100, recomputed by the backend on every read rather than stored. */
  matchScore: number;
  /** The four parts of matchScore: specialty, distance, completeness, verified. */
  matchBreakdown: [number, number, number, number];
  /** Null when the source published no location for this facility. */
  coordinates: { lat: number; lng: number } | null;
}

/** Mirrors the backend ProviderSearchRequest. */
export interface ProviderSearchParams {
  location?: string;
  latitude?: number;
  longitude?: number;
  radiusKm: number;
  specialty?: string;
  findingId?: string;
  availability?: string;
  kinds?: ProviderKind[];
}

/** One recorded search and its ranked results. */
export interface ProviderSearchResult {
  searchId: string;
  /** The place name as typed, saved to the patient's provider-search history. */
  locationQuery: string;
  /** Where the place name resolved to; null when the source omitted it. */
  origin: { lat: number; lng: number } | null;
  radiusKm: number | null;
  availability: string | null;
  /** Stored scope, e.g. "hospital" or "doctor:cardiology". */
  scope: string;
  /** `scope` split into its parts. */
  scopeKind: ProviderKind | "";
  scopeSpecialty: string | null;
  providers: Provider[];
}

/** A previous search, without its results. */
export interface ProviderSearchHistoryEntry {
  searchId: string;
  locationQuery: string;
  scope: string;
  radiusKm: number | null;
  availability: string | null;
  resultCount: number;
  searchedOn: string;
}

export interface DashboardMetric {
  id: string;
  kind: "documents" | "events" | "medications" | "findings" | "priority";
  label: string;
  value: string;
  delta: string;
}

export interface UserProfile {
  /** Patient ID shown on the profile screen, e.g. "MG-2026-004182". */
  id: string;
  /** Short display name used in the sidebar. */
  fullName: string;
  legalName: string;
  initials: string;
  email: string;
  phone: string;
  dateOfBirth: string;
  language: string;
  memberSince: string;
  accountType: string;
}

export interface SecuritySession {
  id: string;
  device: string;
  location: string;
  lastActive: string;
  current: boolean;
}
