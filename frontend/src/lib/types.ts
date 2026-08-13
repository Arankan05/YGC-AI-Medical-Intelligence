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
  pages: number;
  sizeLabel: string;
  status: DocumentStatus;
  source: "digital" | "scanned";
  extractedItems?: number;
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
  status: "active" | "stopped";
  flags: MedicationFlagKind[];
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

export interface LabResult {
  id: string;
  name: string;
  unit: string;
  referenceRange: string;
  referenceLow?: number;
  referenceHigh?: number;
  latestValue: number;
  /** Preserves trailing zeros the lab reported, e.g. "1.0". */
  latestValueLabel: string;
  latestDate: string;
  sourceDocument: string;
  trend: "rising" | "falling" | "stable";
  /** Drives the pill colour: ok = green, medium = amber, high = red. */
  severity: "ok" | "medium" | "high";
  /** e.g. "Below range", "Above range", "Normal". */
  statusLabel: string;
  /** e.g. "Declining · 3 tests". */
  trendLabel: string;
  points: LabPoint[];
}

export interface LabPoint {
  date: string;
  value: number;
  documentId: string;
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

export interface Provider {
  id: string;
  name: string;
  kind: ProviderKind;
  specialties: string[];
  address: string;
  distanceKm: number;
  openingHours?: string;
  phone?: string;
  website?: string;
  matchScore: number;
  /** Ranking weights in the "Why ranked here" bar: specialty, distance, completeness, other. */
  matchBreakdown: [number, number, number, number];
  coordinates: { lat: number; lng: number };
  /** Position of the marker on the map panel, in percent of the map box. */
  mapPosition: { top: number; left: number };
}

export interface ProviderSearchParams {
  location: string;
  radiusKm: number;
  specialty: string;
  kinds: ProviderKind[];
  openNow: boolean;
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
