/**
 * Backend integration points for MediGuardian AI.
 *
 * All authenticated operations obtain the verified Supabase JWT Bearer token
 * and dispatch real HTTP requests to the FastAPI backend at NEXT_PUBLIC_API_URL.
 */

import { getAccessToken, getSupabase } from "@/lib/supabase";
import type {
  AIAnalysisRecord,
  AllergyRecord,
  ChatMessage,
  CrossCheckIssue,
  DocumentDetail,
  DocumentStatus,
  DocumentType,
  Finding,
  LabIntelligenceOverview,
  LabResult,
  LabStatus,
  LabTrend,
  LabTrendDirection,
  LabTrendPoint,
  MedicalDocument,
  MedicalOverview,
  Medication,
  MedicationFlagKind,
  MedicationSafetyReport,
  Provider,
  ProviderKind,
  ProviderSearchHistoryEntry,
  ProviderSearchParams,
  ProviderSearchResult,
  RiskLevel,
  TimelineEvent,
  TimelineEventKind,
  UserProfile,
} from "@/lib/types";

export class ApiNotConfiguredError extends Error {
  constructor(operation: string) {
    super(`"${operation}" is not connected to a backend yet.`);
    this.name = "ApiNotConfiguredError";
  }
}

/**
 * The place name could not be resolved.
 *
 * A correct negative answer from the geocoder, not an outage — the remedy is a
 * different search term, not a retry.
 */
export class LocationNotFoundError extends Error {
  constructor(location: string) {
    super(`We could not find "${location}".`);
    this.name = "LocationNotFoundError";
  }
}

/**
 * An upstream directory service could not be reached.
 *
 * This means "we do not know", never "there is nothing there". It must never be
 * presented to a patient as an empty set of providers.
 */
export class ProviderDirectoryUnavailableError extends Error {
  constructor(message?: string) {
    super(message || "The healthcare directory is temporarily unavailable.");
    this.name = "ProviderDirectoryUnavailableError";
  }
}

export interface SignInInput {
  email: string;
  password: string;
  keepSignedIn?: boolean;
}

export interface SignUpInput {
  fullName: string;
  email: string;
  password: string;
  acknowledgedDisclaimer?: boolean;
}

export interface UploadDocumentInput {
  file: File;
  documentType?: string;
  documentDate?: string;
}

export interface AskAiInput {
  question: string;
  conversationId?: string;
}

export interface MediGuardianApi {
  signIn(input: SignInInput): Promise<void>;
  signUp(input: SignUpInput): Promise<void>;
  signOut(): Promise<void>;

  listDocuments(): Promise<MedicalDocument[]>;
  uploadDocument(
    input: UploadDocumentInput,
    onProgress?: (percent: number) => void
  ): Promise<MedicalDocument>;
  deleteDocument(documentId: string): Promise<void>;
  retryDocument(documentId: string): Promise<void>;
  extractDocument(documentId: string): Promise<void>;
  getDocument(documentId: string): Promise<DocumentDetail>;

  getOverview(): Promise<MedicalOverview>;
  listTimeline(): Promise<TimelineEvent[]>;
  /**
   * Pass an already-fetched safety report to derive medication flags from it,
   * so a caller that also needs the report does not request it twice.
   */
  listMedications(safetyReport?: MedicationSafetyReport): Promise<Medication[]>;
  listCrossCheckIssues(): Promise<CrossCheckIssue[]>;
  runMedicationSafetyCheck(): Promise<MedicationSafetyReport>;
  listLabResults(): Promise<LabResult[]>;
  /** GET /api/lab-intelligence/overview — analysed results + available tests. */
  getLabIntelligenceOverview(): Promise<LabIntelligenceOverview>;
  /** GET /api/lab-intelligence/trends — one trend per test. */
  listLabTrends(): Promise<LabTrend[]>;
  /** GET /api/lab-intelligence/trends/{test_name}; null when the test is absent. */
  getLabTrend(testName: string): Promise<LabTrend | null>;
  /** Overview and trends folded into one row per test for the lab table. */
  listLabIntelligence(): Promise<LabResult[]>;
  listFindings(): Promise<Finding[]>;
  listAllergies(): Promise<AllergyRecord[]>;
  listAnalyses(): Promise<AIAnalysisRecord[]>;
  listNotifications(): Promise<Finding[]>;
  getFinding(findingId: string): Promise<Finding>;

  askAi(input: AskAiInput): Promise<ChatMessage>;

  /**
   * POST /api/doctor-search/search — resolves the location, queries
   * OpenStreetMap and records the search.
   *
   * Throws LocationNotFoundError when the place name is unknown and
   * ProviderDirectoryUnavailableError when an upstream service is down. An
   * empty `providers` array is a real answer: no facilities were found there.
   */
  searchProviders(params: ProviderSearchParams): Promise<ProviderSearchResult>;
  /** GET /api/doctor-search/history — previous searches, most recent first. */
  listProviderSearches(limit?: number): Promise<ProviderSearchHistoryEntry[]>;
  /** GET /api/doctor-search/searches/{id}; null when it is not this patient's. */
  getProviderSearch(searchId: string): Promise<ProviderSearchResult | null>;

  getProfile(): Promise<UserProfile>;
  updateProfile(profile: Partial<UserProfile>): Promise<UserProfile>;
  changePassword(input: {
    currentPassword: string;
    newPassword: string;
  }): Promise<void>;
  revokeSession(sessionId: string): Promise<void>;
  exportAccountData(): Promise<Blob>;
  deleteAccount(): Promise<void>;
}

function unconfigured<K extends keyof MediGuardianApi>(operation: K) {
  return (() =>
    Promise.reject(new ApiNotConfiguredError(operation))) as MediGuardianApi[K];
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

function formatDate(isoString?: string | null): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return isoString;
  }
}

function getInitials(name?: string | null): string {
  if (!name || !name.trim()) return "U";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function mapDocumentType(docType: string): DocumentType {
  const clean = (docType || "").toLowerCase().replace(/[_-]/g, " ");
  if (clean.includes("prescription")) return "Prescription";
  if (clean.includes("lab")) return "Lab Report";
  if (clean.includes("discharge")) return "Discharge Summary";
  if (
    clean.includes("scan") ||
    clean.includes("imaging") ||
    clean.includes("xray") ||
    clean.includes("mri")
  ) {
    return "Imaging Report";
  }
  return "Doctor Note";
}

function mapDocumentStatus(status: string): DocumentStatus {
  const s = (status || "").toUpperCase();
  if (s === "UPLOADED" || s === "PROCESSING") return "processing";
  if (s === "EXTRACTING") return "extracting";
  if (s === "ANALYZING") return "analyzing";
  if (s === "COMPLETED") return "completed";
  if (s === "FAILED") return "failed";
  return "completed";
}

interface BackendDocumentResponse {
  id: string;
  patient_id?: string;
  file_name: string;
  file_path?: string;
  document_type: string;
  processing_status: string;
  uploaded_at: string;
  processed_at?: string | null;
  error_message?: string | null;
  page_count?: number;
  has_text?: boolean;
}

function mapDocument(doc: BackendDocumentResponse): MedicalDocument {
  return {
    id: String(doc.id),
    title: doc.file_name || "Medical Document",
    type: mapDocumentType(doc.document_type || "unknown"),
    provider: "Medical Record",
    documentDate: formatDate(doc.uploaded_at),
    uploadedAt: formatDate(doc.uploaded_at),
    pages: doc.page_count ?? 1,
    sizeLabel: "Uploaded file",
    status: mapDocumentStatus(doc.processing_status || "COMPLETED"),
    source: doc.document_type === "scanned_document" ? "scanned" : "digital",
    extractedItems: doc.processing_status === "COMPLETED" ? 1 : undefined,
  };
}

const FLAG_KINDS: MedicationFlagKind[] = [
  "interaction",
  "duplicate",
  "dosage",
  "allergy",
];

function mapRiskLevel(value?: string | null): RiskLevel {
  const risk = (value || "low").toLowerCase();
  return risk === "high" || risk === "medium" || risk === "low"
    ? (risk as RiskLevel)
    : "low";
}

function mapFlagKind(kind: string, findingType: string): MedicationFlagKind {
  const value = (kind || "").toLowerCase();
  if ((FLAG_KINDS as string[]).includes(value)) {
    return value as MedicationFlagKind;
  }
  // Fall back to the finding_type substrings the findings mapper already reads.
  const type = (findingType || "").toLowerCase();
  if (type.includes("allergy")) return "allergy";
  if (type.includes("duplicate")) return "duplicate";
  if (type.includes("dosage")) return "dosage";
  return "interaction";
}

interface BackendSafetyIssueResponse {
  id: string;
  kind: string;
  finding_type: string;
  risk_level: string;
  title: string;
  medications?: string[] | null;
  description: string;
  recommendation?: string | null;
  confidence?: number | null;
}

interface BackendMedicationSafetyReportResponse {
  reference_date: string;
  active_medication_count?: number;
  active_medications?: string[] | null;
  finding_count?: number;
  highest_risk_level?: string | null;
  issues?: BackendSafetyIssueResponse[] | null;
}

function mapSafetyIssue(item: BackendSafetyIssueResponse): CrossCheckIssue {
  return {
    id: String(item.id),
    kind: mapFlagKind(item.kind, item.finding_type),
    risk: mapRiskLevel(item.risk_level),
    title: item.title || "Medication safety issue",
    medications: item.medications || [],
    explanation: item.description || "",
    recommendation:
      item.recommendation || "Discuss this with your doctor or pharmacist.",
    // The backend already reports confidence as a 0–1 fraction.
    confidence: typeof item.confidence === "number" ? item.confidence : 0.9,
  };
}

function mapMedicationSafetyReport(
  data: BackendMedicationSafetyReportResponse
): MedicationSafetyReport {
  const issues = (data.issues || []).map(mapSafetyIssue);
  return {
    referenceDate: formatDate(data.reference_date),
    activeMedicationCount: data.active_medication_count || 0,
    activeMedications: data.active_medications || [],
    findingCount: data.finding_count ?? issues.length,
    highestRiskLevel: data.highest_risk_level
      ? mapRiskLevel(data.highest_risk_level)
      : null,
    issues,
  };
}

function emptyMedicationSafetyReport(): MedicationSafetyReport {
  return {
    referenceDate: formatDate(null),
    activeMedicationCount: 0,
    activeMedications: [],
    findingCount: 0,
    highestRiskLevel: null,
    issues: [],
  };
}

function normalizeMedicationKey(value?: string | null): string {
  return (value || "").trim().toLowerCase();
}

/**
 * Indexes safety issues by the medications they involve, so each medication row
 * can show its own flags.
 *
 * Issues carry both the display names recorded on the source document and a
 * stable id whose suffix holds the normalized generic names, e.g.
 * "drug_interaction:aspirin+warfarin". Both are indexed, so a medication matches
 * whether it was recorded under a generic or a brand label.
 */
function buildMedicationFlagIndex(
  issues: CrossCheckIssue[]
): Map<string, MedicationFlagKind[]> {
  const index = new Map<string, MedicationFlagKind[]>();

  function add(key: string, kind: MedicationFlagKind) {
    if (!key) return;
    const existing = index.get(key);
    if (!existing) {
      index.set(key, [kind]);
    } else if (!existing.includes(kind)) {
      existing.push(kind);
    }
  }

  for (const issue of issues) {
    for (const name of issue.medications) {
      add(normalizeMedicationKey(name), issue.kind);
    }
    const separator = issue.id.indexOf(":");
    const subject = separator >= 0 ? issue.id.slice(separator + 1) : "";
    for (const token of subject.split("+")) {
      add(normalizeMedicationKey(token), issue.kind);
    }
  }

  return index;
}

interface BackendMedicationResponse {
  id: string;
  name: string;
  normalized_name: string;
  dosage?: string | null;
  frequency?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  instructions?: string | null;
  source_document_id?: string | null;
  source_document_name?: string | null;
  status: string;
  created_at: string;
}

function mapMedication(
  item: BackendMedicationResponse,
  flagIndex?: Map<string, MedicationFlagKind[]>
): Medication {
  const flags: MedicationFlagKind[] = flagIndex
    ? Array.from(
        new Set([
          ...(flagIndex.get(normalizeMedicationKey(item.name)) || []),
          ...(flagIndex.get(normalizeMedicationKey(item.normalized_name)) || []),
        ])
      )
    : [];
  return {
    id: String(item.id),
    name: item.name || "Medication",
    genericName: item.normalized_name || item.name || "Medication",
    dosage: item.dosage || "As prescribed",
    frequency: item.frequency || "Daily",
    startedOn: formatDate(item.start_date || item.created_at),
    prescribedBy: item.source_document_name ? `From ${item.source_document_name}` : "Clinical Record",
    sourceDocumentId: item.source_document_id ? String(item.source_document_id) : "",
    sourceDocumentName: item.source_document_name || undefined,
    instructions: item.instructions || undefined,
    status: item.status === "stopped" ? "stopped" : "active",
    flags,
  };
}

interface BackendFindingResponse {
  id: string;
  finding_type: string;
  title: string;
  description: string;
  risk_level?: string | null;
  confidence?: number | null;
  recommendation?: string | null;
  created_at: string;
}

function mapFinding(item: BackendFindingResponse): Finding {
  const riskRaw = (item.risk_level || "low").toLowerCase();
  const risk: RiskLevel = riskRaw === "high" || riskRaw === "medium" || riskRaw === "low" ? (riskRaw as RiskLevel) : "low";
  const typeLower = (item.finding_type || "").toLowerCase();

  let category: MedicationFlagKind | "lab-trend" | "follow-up" = "follow-up";
  let categoryLabel = "CLINICAL FINDING";
  let categoryName = "Clinical Finding";

  if (typeLower.includes("allergy")) {
    category = "allergy";
    categoryLabel = "ALLERGY CHECK";
    categoryName = "Allergy / Contradiction";
  } else if (typeLower.includes("interaction") || typeLower.includes("contraindication")) {
    category = "interaction";
    categoryLabel = "DRUG INTERACTION";
    categoryName = "Medication Interaction";
  } else if (typeLower.includes("duplicate")) {
    category = "duplicate";
    categoryLabel = "DUPLICATE CHECK";
    categoryName = "Duplicate Therapy";
  } else if (typeLower.includes("dosage")) {
    category = "dosage";
    categoryLabel = "DOSAGE CHECK";
    categoryName = "Dosage Conflict";
  } else if (typeLower.includes("lab")) {
    category = "lab-trend";
    categoryLabel = "LAB TREND";
    categoryName = "Biomarker Trend";
  }

  const confidencePct = typeof item.confidence === "number" ? Math.round(item.confidence <= 1 ? item.confidence * 100 : item.confidence) : 90;

  return {
    id: String(item.id),
    title: item.title || "Clinical Finding",
    category,
    categoryLabel,
    categoryName,
    risk,
    confidence: confidencePct,
    summary: item.description || "",
    detectedOn: formatDate(item.created_at),
    detectedAt: formatDate(item.created_at),
    documentsInvolved: "Extracted from medical records",
    reviewStatus: "AI-extracted · Review with physician",
    guidance: item.recommendation || "Verify with a qualified healthcare professional.",
    relatedMedications: [],
    evidence: [],
    whatThisMeans: item.description || "",
    determination: [
      { kind: "ai", text: "AI-extracted and structured by MediGuardian Intelligence Layer." },
    ],
    contributingFactors: [],
    recommendedAction: item.recommendation || "Discuss with your physician during your next consultation.",
    suitableProfessional: {
      title: "Prescribing Physician / Specialist",
      rationale: "Can review dosage, clinical context, and alternatives.",
    },
    providerCta: { label: "Find Healthcare Provider", primary: true },
  };
}

interface BackendLabResultResponse {
  id: string;
  test_name: string;
  value: string;
  unit?: string | null;
  reference_range?: string | null;
  result_date?: string | null;
  source_document_id?: string | null;
  source_document_name?: string | null;
  created_at: string;
}

/**
 * Read a laboratory value only when it is unambiguously one exact number.
 *
 * Mirrors LabIntelligenceService._parse_numeric_value. `parseFloat` is not safe
 * here: it reads "1,200" as 1 and ">1000" as NaN inconsistently, and a censored
 * "<0.01" is a detection limit, not the measurement 0.01.
 */
function parseExactNumber(value: string | null | undefined): number | null {
  if (!value) return null;
  const text = String(value).trim();
  if (!text) return null;
  if (/[<>≤≥~±,]/.test(text)) return null;
  const match = /^([-+]?(?:\d+(?:\.\d+)?|\.\d+))(?:\s*[A-Za-z%/^([].*)?$/.exec(text);
  if (!match) return null;
  if (/^[-+]?(?:\d+(?:\.\d+)?|\.\d+)[eE][-+]?\d+$/.test(text)) return null;
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Maps a plain record from /api/records/lab-results.
 *
 * That endpoint stores values but does not classify them, so status is UNKNOWN
 * and trend is INSUFFICIENT_DATA — the honest description of what it knows.
 * Intelligence comes from /api/lab-intelligence, mapped below.
 */
function mapLabResult(item: BackendLabResultResponse): LabResult {
  const numeric = parseExactNumber(item.value);
  const date = formatDate(item.result_date || item.created_at);
  return {
    id: String(item.id),
    name: item.test_name || "Diagnostic Test",
    unit: item.unit || "",
    referenceRange: item.reference_range || "—",
    latestValue: numeric,
    latestValueLabel: item.value || "—",
    latestDate: date,
    sourceDocument: item.source_document_name || "Lab Report",
    sourceDocumentId: item.source_document_id ? String(item.source_document_id) : null,
    trend: "INSUFFICIENT_DATA",
    status: "UNKNOWN",
    points: [
      {
        date,
        value: numeric,
        valueLabel: item.value || "—",
        status: "UNKNOWN",
        documentId: item.source_document_id ? String(item.source_document_id) : null,
        documentName: item.source_document_name || null,
      },
    ],
  };
}

// ----------------------------------------------------------------------
// Lab intelligence
// ----------------------------------------------------------------------

interface BackendLabAnalysisResponse {
  id: string;
  test_name: string;
  value: string;
  numeric_value?: number | null;
  unit?: string | null;
  reference_range?: string | null;
  result_date?: string | null;
  status: LabStatus;
  source_document_id?: string | null;
  source_document_name?: string | null;
}

interface BackendLabTrendPointResponse {
  result_date?: string | null;
  value: string;
  numeric_value?: number | null;
  unit?: string | null;
  status: LabStatus;
  source_document_id?: string | null;
  source_document_name?: string | null;
}

interface BackendLabTrendResponse {
  test_name: string;
  unit?: string | null;
  trend: LabTrendDirection;
  points: BackendLabTrendPointResponse[];
}

interface BackendLabOverviewResponse {
  results: BackendLabAnalysisResponse[];
  available_tests: string[];
}

/**
 * Backend states are passed through verbatim. Anything unrecognised degrades to
 * UNKNOWN / INSUFFICIENT_DATA rather than to a confident value.
 */
function toLabStatus(value: unknown): LabStatus {
  return value === "NORMAL" || value === "HIGH" || value === "LOW"
    ? value
    : "UNKNOWN";
}

function toLabTrend(value: unknown): LabTrendDirection {
  return value === "INCREASING" || value === "DECREASING" || value === "STABLE"
    ? value
    : "INSUFFICIENT_DATA";
}

function mapLabTrendPoint(point: BackendLabTrendPointResponse): LabTrendPoint {
  return {
    date: formatDate(point.result_date),
    value: point.numeric_value ?? null,
    valueLabel: point.value || "—",
    status: toLabStatus(point.status),
    documentId: point.source_document_id ? String(point.source_document_id) : null,
    documentName: point.source_document_name || null,
  };
}

function mapLabTrend(trend: BackendLabTrendResponse): LabTrend {
  return {
    testName: trend.test_name,
    unit: trend.unit || null,
    trend: toLabTrend(trend.trend),
    points: (trend.points || []).map(mapLabTrendPoint),
  };
}

function mapLabOverview(data: BackendLabOverviewResponse): LabIntelligenceOverview {
  return {
    results: (data?.results || []).map((item) => ({
      id: String(item.id),
      name: item.test_name || "Diagnostic Test",
      unit: item.unit || "",
      referenceRange: item.reference_range || "—",
      latestValue: item.numeric_value ?? null,
      latestValueLabel: item.value || "—",
      latestDate: formatDate(item.result_date),
      sourceDocument: item.source_document_name || "",
      sourceDocumentId: item.source_document_id ? String(item.source_document_id) : null,
      status: toLabStatus(item.status),
      trend: "INSUFFICIENT_DATA",
      points: [],
    })),
    availableTests: data?.available_tests || [],
  };
}

/**
 * Folds the per-test trends into the per-test rows the lab results table shows.
 *
 * The overview is per result; the table is per test. The newest analysed result
 * for a test supplies value/status, its trend supplies direction and history.
 */
function mergeLabIntelligence(
  overview: LabIntelligenceOverview,
  trends: LabTrend[]
): LabResult[] {
  const trendByTest = new Map(trends.map((t) => [t.testName.trim().toLowerCase(), t]));
  const seen = new Set<string>();
  const rows: LabResult[] = [];

  // overview.results arrive newest first, so the first row per test is latest.
  for (const result of overview.results) {
    const key = result.name.trim().toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);

    const trend = trendByTest.get(key);
    rows.push({
      ...result,
      trend: trend ? trend.trend : "INSUFFICIENT_DATA",
      unit: result.unit || trend?.unit || "",
      points: trend ? trend.points : [],
    });
  }

  return rows;
}

// ----------------------------------------------------------------------
// Healthcare providers
// ----------------------------------------------------------------------

interface BackendMatchBreakdownResponse {
  specialty: number;
  distance: number;
  completeness: number;
  verified: number;
}

interface BackendProviderResponse {
  id: string;
  provider_name: string;
  kind: string;
  specialties?: string[] | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  distance_km?: number | null;
  phone?: string | null;
  website?: string | null;
  opening_hours?: string | null;
  source: string;
  match_score: number;
  match_breakdown: BackendMatchBreakdownResponse;
  created_at: string;
}

interface BackendDoctorSearchSummaryResponse {
  id: string;
  specialty: string;
  location_query: string;
  latitude?: number | null;
  longitude?: number | null;
  availability_preference?: string | null;
  search_radius?: number | null;
  finding_id?: string | null;
  result_count?: number;
  created_at: string;
}

interface BackendDoctorSearchResponse {
  search: BackendDoctorSearchSummaryResponse;
  recommendations?: BackendProviderResponse[] | null;
}

const PROVIDER_KINDS: ProviderKind[] = [
  "hospital",
  "clinic",
  "doctor",
  "pharmacy",
  "laboratory",
];

/**
 * Backend categories are passed through verbatim. An unrecognised one degrades
 * to "" so the row still renders, rather than being relabelled as some other
 * kind of facility.
 */
function toProviderKind(value: unknown): ProviderKind | "" {
  return (PROVIDER_KINDS as string[]).includes(String(value))
    ? (value as ProviderKind)
    : "";
}

/**
 * Splits the stored scope, e.g. "hospital" or "doctor:cardiology".
 *
 * Mirrors ProviderDiscoveryService.parse_search_scope. An unreadable scope
 * yields no kind rather than a guess.
 */
function parseScope(scope: string | null | undefined): {
  kind: ProviderKind | "";
  specialty: string | null;
} {
  const text = (scope || "").trim().toLowerCase();
  if (!text) return { kind: "", specialty: null };
  const separator = text.indexOf(":");
  const kind = toProviderKind(separator >= 0 ? text.slice(0, separator) : text);
  const specialty = separator >= 0 ? text.slice(separator + 1).trim() : "";
  return { kind, specialty: kind && specialty ? specialty : null };
}

/** Null stays null: a detail the source did not publish is not filled in. */
function optionalText(value: string | null | undefined): string | null {
  const text = (value || "").trim();
  return text || null;
}

function mapProvider(item: BackendProviderResponse): Provider {
  const hasCoordinates =
    typeof item.latitude === "number" && typeof item.longitude === "number";
  const breakdown = item.match_breakdown;

  return {
    id: String(item.id),
    name: item.provider_name,
    kind: toProviderKind(item.kind),
    specialties: item.specialties || [],
    address: optionalText(item.address),
    distanceKm: typeof item.distance_km === "number" ? item.distance_km : null,
    openingHours: optionalText(item.opening_hours),
    phone: optionalText(item.phone),
    website: optionalText(item.website),
    matchScore: Math.round(item.match_score ?? 0),
    matchBreakdown: [
      breakdown?.specialty ?? 0,
      breakdown?.distance ?? 0,
      breakdown?.completeness ?? 0,
      breakdown?.verified ?? 0,
    ],
    coordinates: hasCoordinates
      ? { lat: item.latitude as number, lng: item.longitude as number }
      : null,
  };
}

function mapProviderSearch(
  data: BackendDoctorSearchResponse
): ProviderSearchResult {
  const search = data.search;
  const scope = parseScope(search.specialty);
  const hasOrigin =
    typeof search.latitude === "number" && typeof search.longitude === "number";

  return {
    searchId: String(search.id),
    locationQuery: search.location_query,
    origin: hasOrigin
      ? { lat: search.latitude as number, lng: search.longitude as number }
      : null,
    radiusKm: typeof search.search_radius === "number" ? search.search_radius : null,
    availability: optionalText(search.availability_preference),
    scope: search.specialty,
    scopeKind: scope.kind,
    scopeSpecialty: scope.specialty,
    providers: (data.recommendations || []).map(mapProvider),
  };
}

function mapProviderHistoryEntry(
  item: BackendDoctorSearchSummaryResponse
): ProviderSearchHistoryEntry {
  return {
    searchId: String(item.id),
    locationQuery: item.location_query,
    scope: item.specialty,
    radiusKm: typeof item.search_radius === "number" ? item.search_radius : null,
    availability: optionalText(item.availability_preference),
    resultCount: item.result_count ?? 0,
    searchedOn: formatDate(item.created_at),
  };
}

interface BackendMedicalEventResponse {
  id: string;
  event_type: string;
  event_date?: string | null;
  title: string;
  description?: string | null;
  source_document_id?: string | null;
  source_document_name?: string | null;
  created_at: string;
}

function mapTimelineEvent(item: BackendMedicalEventResponse): TimelineEvent {
  const typeLower = (item.event_type || "").toLowerCase();
  let kind: TimelineEventKind = "note";
  if (typeLower.includes("prescript") || typeLower.includes("med")) kind = "prescription";
  else if (typeLower.includes("lab")) kind = "lab";
  else if (typeLower.includes("imag") || typeLower.includes("xray") || typeLower.includes("scan")) kind = "imaging";
  else if (typeLower.includes("visit") || typeLower.includes("admiss") || typeLower.includes("consult")) kind = "visit";

  return {
    id: String(item.id),
    date: formatDate(item.event_date || item.created_at),
    kind,
    title: item.title || "Medical Event",
    provider: item.source_document_name ? `From: ${item.source_document_name}` : "Medical Record",
    summary: item.description || "",
    documentTitle: item.source_document_name || "Document",
    documentId: String(item.source_document_id || ""),
    tags: [kind.toUpperCase()],
  };
}

interface BackendAllergyResponse {
  id: string;
  medication_name: string;
  normalized_medication_name: string;
  reaction?: string | null;
  severity?: string | null;
  source_document_id?: string | null;
  created_at: string;
}

function mapAllergy(item: BackendAllergyResponse): AllergyRecord {
  return {
    id: String(item.id),
    medicationName: item.medication_name,
    normalizedMedicationName: item.normalized_medication_name || item.medication_name,
    reaction: item.reaction || undefined,
    severity: item.severity || "moderate",
    sourceDocumentId: item.source_document_id ? String(item.source_document_id) : undefined,
    recordedDate: formatDate(item.created_at),
    createdAt: item.created_at,
  };
}

interface BackendAIAnalysisResponse {
  id: string;
  analysis_type: string;
  result: Record<string, unknown>;
  confidence?: number | null;
  created_at: string;
}

function mapAIAnalysis(item: BackendAIAnalysisResponse): AIAnalysisRecord {
  const resObj = typeof item.result === "object" && item.result !== null ? item.result : {};
  const summary = typeof resObj.summary === "string" ? resObj.summary : undefined;
  const rawConfidence = typeof item.confidence === "number" ? item.confidence : (typeof resObj.confidence === "number" ? resObj.confidence : undefined);
  const confidencePct =
    typeof rawConfidence === "number"
      ? Math.round(rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence)
      : undefined;

  return {
    id: String(item.id),
    analysisType: item.analysis_type || "document_extraction",
    result: resObj,
    confidence: confidencePct,
    summary,
    createdAt: formatDate(item.created_at),
  };
}

interface BackendChatCitationResponse {
  document_id?: string | null;
  documentId?: string | null;
  document_title?: string | null;
  documentTitle?: string | null;
  page?: number | null;
  quote?: string | null;
}

interface BackendChatRefusalResponse {
  overline?: string | null;
  headline?: string | null;
  suggestions?: string[] | null;
  footnote?: string | null;
}

interface BackendChatCtaResponse {
  label?: string | null;
  note?: string | null;
}

interface BackendChatMessageResponse {
  id: string;
  role?: string | null;
  paragraphs?: string[] | null;
  citations?: BackendChatCitationResponse[] | null;
  confidence?: number | null;
  guidance?: string | null;
  refusal?: BackendChatRefusalResponse | null;
  cta?: BackendChatCtaResponse | null;
}

function mapChatMessage(item: BackendChatMessageResponse): ChatMessage {
  const citations = (item.citations || []).map((c) => ({
    documentId: c.documentId || c.document_id || "",
    documentTitle: c.documentTitle || c.document_title || "Document",
    page: typeof c.page === "number" ? c.page : 1,
    quote: c.quote || "",
  }));

  const refusal =
    item.refusal && item.refusal.headline
      ? {
          overline: item.refusal.overline || "SAFETY NOTICE",
          headline: item.refusal.headline,
          suggestions: item.refusal.suggestions || [],
          footnote:
            item.refusal.footnote ||
            "This assistant explains recorded medical history and does not diagnose or prescribe.",
        }
      : undefined;

  const cta =
    item.cta && item.cta.label
      ? {
          label: item.cta.label,
          note: item.cta.note || "Consult a healthcare professional",
        }
      : undefined;

  return {
    id: String(item.id),
    role: "assistant",
    paragraphs:
      item.paragraphs && item.paragraphs.length > 0
        ? item.paragraphs
        : ["No additional details available from your medical records."],
    citations: citations.length > 0 ? citations : undefined,
    confidence: typeof item.confidence === "number" ? item.confidence : undefined,
    guidance: item.guidance || undefined,
    refusal,
    cta,
  };
}

async function authFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = await getAccessToken();
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  return response;
}

const defaultApiImplementation: MediGuardianApi = {
  async signIn(input: SignInInput): Promise<void> {
    const sb = getSupabase();
    const { data, error } = await sb.auth.signInWithPassword({
      email: input.email,
      password: input.password,
    });
    if (error) {
      throw new Error(error.message);
    }
    if (!data.session) {
      throw new Error("Failed to start session. Please try again.");
    }
    // Sync application User & Patient records in PostgreSQL asynchronously in background (non-blocking)
    void authFetch("/api/auth/register", { method: "POST" }).catch(() => {
      // Non-fatal if already registered or network transient
    });
  },

  async signUp(input: SignUpInput): Promise<void> {
    const sb = getSupabase();
    const { data, error } = await sb.auth.signUp({
      email: input.email,
      password: input.password,
      options: {
        data: {
          full_name: input.fullName,
          acknowledged_disclaimer: input.acknowledgedDisclaimer,
        },
      },
    });
    if (error) {
      throw new Error(error.message);
    }
    // Check if session was created; if not, attempt auto sign-in
    if (!data.session) {
      const { data: signInData, error: signInError } =
        await sb.auth.signInWithPassword({
          email: input.email,
          password: input.password,
        });
      if (signInError || !signInData.session) {
        throw new Error(
          "Account created! Please check your email to confirm your account before signing in."
        );
      }
    }
    // Sync to PostgreSQL
    try {
      await authFetch("/api/auth/register", { method: "POST" });
    } catch {
      // Handled on sign-in
    }
  },

  async signOut(): Promise<void> {
    const sb = getSupabase();
    const { error } = await sb.auth.signOut();
    if (error) {
      throw new Error(error.message);
    }
  },

  async listDocuments(): Promise<MedicalDocument[]> {
    const res = await authFetch("/api/documents", { method: "GET" });
    if (res.status === 401) {
      return [];
    }
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch documents." }));
      throw new Error(err.detail || "Failed to fetch documents.");
    }
    const data = await res.json();
    return (data.items || []).map(mapDocument);
  },

  async uploadDocument(
    input: UploadDocumentInput,
    onProgress?: (percent: number) => void
  ): Promise<MedicalDocument> {
    const token = await getAccessToken();
    if (!token) {
      console.warn("[uploadDocument] Auth check failed: No active Supabase access token found.");
      throw new Error(
        "Authentication credentials were not provided. Please sign in and try again."
      );
    }

    const formData = new FormData();
    formData.append("file", input.file);

    if (input.documentType) {
      let docType = input.documentType.toLowerCase().replace(/[\s-]+/g, "_");
      if (
        ![
          "prescription",
          "lab_report",
          "medical_report",
          "scanned_document",
          "unknown",
        ].includes(docType)
      ) {
        if (docType.includes("lab")) docType = "lab_report";
        else if (docType.includes("prescript")) docType = "prescription";
        else docType = "medical_report";
      }
      formData.append("document_type", docType);
    }

    return new Promise<MedicalDocument>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/api/documents/upload`);
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percent = Math.round((event.loaded / event.total) * 100);
            onProgress(percent);
          }
        };
      }

      xhr.onload = async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            // Automatically trigger AI extraction pipeline on upload
            try {
              if (data.id) {
                await authFetch(`/api/documents/${data.id}/extract`, {
                  method: "POST",
                });
              }
            } catch {
              // Extraction trigger failure is non-fatal for upload
            }
            resolve(mapDocument(data));
          } catch {
            reject(
              new Error("Failed to parse server response after document upload.")
            );
          }
        } else {
          try {
            const errorJson = JSON.parse(xhr.responseText);
            reject(
              new Error(
                errorJson.detail || `Upload failed with status ${xhr.status}`
              )
            );
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      };

      xhr.onerror = () => {
        reject(new Error("Network error during document upload."));
      };

      xhr.send(formData);
    });
  },

  async deleteDocument(documentId: string): Promise<void> {
    const res = await authFetch(`/api/documents/${documentId}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to delete document." }));
      throw new Error(err.detail || "Failed to delete document.");
    }
  },

  async retryDocument(documentId: string): Promise<void> {
    const res = await authFetch(`/api/documents/${documentId}/process`, {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to process document." }));
      throw new Error(err.detail || "Failed to process document.");
    }
  },

  async extractDocument(documentId: string): Promise<void> {
    const res = await authFetch(`/api/documents/${documentId}/extract`, {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to extract medical data with AI." }));
      throw new Error(err.detail || "Failed to extract medical data with AI.");
    }
  },

  async getDocument(documentId: string): Promise<DocumentDetail> {
    const res = await authFetch(`/api/documents/${documentId}`, { method: "GET" });
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch document details." }));
      throw new Error(err.detail || "Failed to fetch document details.");
    }
    const data = await res.json();
    const baseDoc = mapDocument(data);
    const confidencePct =
      typeof data.ai_confidence === "number"
        ? Math.round(data.ai_confidence <= 1 ? data.ai_confidence * 100 : data.ai_confidence)
        : undefined;

    return {
      ...baseDoc,
      processedAt: data.processed_at ? formatDate(data.processed_at) : undefined,
      extractedText: data.extracted_text || undefined,
      extractionMethod: data.extraction_method || undefined,
      pageCount: data.page_count || baseDoc.pages,
      medications: (data.medications || []).map((m: BackendMedicationResponse) =>
        mapMedication(m)
      ),
      findings: (data.findings || []).map(mapFinding),
      labResults: (data.lab_results || []).map(mapLabResult),
      allergies: (data.allergies || []).map(mapAllergy),
      events: (data.events || []).map(mapTimelineEvent),
      aiSummary: data.ai_summary || undefined,
      aiConfidence: confidencePct,
    };
  },

  async getOverview(): Promise<MedicalOverview> {
    const res = await authFetch("/api/records/overview", { method: "GET" });
    if (res.status === 401) {
      return {
        patientId: "",
        totalDocuments: 0,
        totalMedications: 0,
        totalFindings: 0,
        totalEvents: 0,
        totalLabResults: 0,
        totalAllergies: 0,
        recentEvents: [],
        activeMedications: [],
        priorityFindings: [],
      };
    }
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch medical overview." }));
      throw new Error(err.detail || "Failed to fetch medical overview.");
    }
    const data = await res.json();
    return {
      patientId: String(data.patient_id || ""),
      totalDocuments: data.total_documents || 0,
      totalMedications: data.total_medications || 0,
      totalFindings: data.total_findings || 0,
      totalEvents: data.total_events || 0,
      totalLabResults: data.total_lab_results || 0,
      totalAllergies: data.total_allergies || 0,
      latestSummary: data.latest_summary || undefined,
      confidenceScore: data.confidence_score ?? undefined,
      recentEvents: (data.recent_events || []).map(mapTimelineEvent),
      activeMedications: (data.active_medications || []).map(
        (m: BackendMedicationResponse) => mapMedication(m)
      ),
      priorityFindings: (data.priority_findings || []).map(mapFinding),
    };
  },

  async listTimeline(): Promise<TimelineEvent[]> {
    const res = await authFetch("/api/records/timeline", { method: "GET" });
    if (res.status === 401) return [];
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch timeline events." }));
      throw new Error(err.detail || "Failed to fetch timeline events.");
    }
    const data = await res.json();
    return (data || []).map(mapTimelineEvent);
  },

  async listMedications(
    safetyReport?: MedicationSafetyReport
  ): Promise<Medication[]> {
    const res = await authFetch("/api/records/medications", { method: "GET" });
    if (res.status === 401) return [];
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch medications." }));
      throw new Error(err.detail || "Failed to fetch medications.");
    }
    const data = await res.json();

    // Safety flags come from the medication safety engine. A caller that already
    // holds a report passes it in; otherwise it is fetched here. A failure must
    // not stop the medication list itself from rendering, so the flags are
    // simply omitted if the check is unavailable.
    let flagIndex: Map<string, MedicationFlagKind[]> | undefined;
    try {
      const report =
        safetyReport ??
        (await defaultApiImplementation.runMedicationSafetyCheck());
      flagIndex = buildMedicationFlagIndex(report.issues);
    } catch {
      flagIndex = undefined;
    }

    return (data || []).map((item: BackendMedicationResponse) =>
      mapMedication(item, flagIndex)
    );
  },

  async listCrossCheckIssues(): Promise<CrossCheckIssue[]> {
    const report = await defaultApiImplementation.runMedicationSafetyCheck();
    return report.issues;
  },

  async runMedicationSafetyCheck(): Promise<MedicationSafetyReport> {
    const res = await authFetch("/api/medication-safety/check", {
      method: "GET",
    });
    if (res.status === 401) return emptyMedicationSafetyReport();
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to run medication safety check." }));
      throw new Error(err.detail || "Failed to run medication safety check.");
    }
    const data = await res.json();
    return mapMedicationSafetyReport(data);
  },

  async listLabResults(): Promise<LabResult[]> {
    const res = await authFetch("/api/records/lab-results", { method: "GET" });
    if (res.status === 401) return [];
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch lab results." }));
      throw new Error(err.detail || "Failed to fetch lab results.");
    }
    const data = await res.json();
    return (data || []).map(mapLabResult);
  },

  async getLabIntelligenceOverview(): Promise<LabIntelligenceOverview> {
    const res = await authFetch("/api/lab-intelligence/overview", {
      method: "GET",
    });
    if (res.status === 401) return { results: [], availableTests: [] };
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch lab intelligence." }));
      throw new Error(err.detail || "Failed to fetch lab intelligence.");
    }
    return mapLabOverview(await res.json());
  },

  async listLabTrends(): Promise<LabTrend[]> {
    const res = await authFetch("/api/lab-intelligence/trends", {
      method: "GET",
    });
    if (res.status === 401) return [];
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch lab trends." }));
      throw new Error(err.detail || "Failed to fetch lab trends.");
    }
    const data = await res.json();
    return (data?.trends || []).map(mapLabTrend);
  },

  async getLabTrend(testName: string): Promise<LabTrend | null> {
    const res = await authFetch(
      `/api/lab-intelligence/trends/${encodeURIComponent(testName)}`,
      { method: "GET" }
    );
    if (res.status === 401) return null;
    // 404 means this patient has no result under that name — an expected
    // outcome, not a failure.
    if (res.status === 404) return null;
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch lab trend." }));
      throw new Error(err.detail || "Failed to fetch lab trend.");
    }
    return mapLabTrend(await res.json());
  },

  async listLabIntelligence(): Promise<LabResult[]> {
    const [overview, trends] = await Promise.all([
      defaultApiImplementation.getLabIntelligenceOverview(),
      defaultApiImplementation.listLabTrends(),
    ]);
    return mergeLabIntelligence(overview, trends);
  },

  async listFindings(): Promise<Finding[]> {
    const res = await authFetch("/api/records/findings", { method: "GET" });
    if (res.status === 401) return [];
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch findings." }));
      throw new Error(err.detail || "Failed to fetch findings.");
    }
    const data = await res.json();
    return (data || []).map(mapFinding);
  },

  async listAllergies(): Promise<AllergyRecord[]> {
    const res = await authFetch("/api/records/allergies", { method: "GET" });
    if (res.status === 401) return [];
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch allergy records." }));
      throw new Error(err.detail || "Failed to fetch allergy records.");
    }
    const data = await res.json();
    return (data || []).map(mapAllergy);
  },

  async listAnalyses(): Promise<AIAnalysisRecord[]> {
    const res = await authFetch("/api/records/analyses", { method: "GET" });
    if (res.status === 401) return [];
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch AI analyses." }));
      throw new Error(err.detail || "Failed to fetch AI analyses.");
    }
    const data = await res.json();
    return (data || []).map(mapAIAnalysis);
  },

  async listNotifications(): Promise<Finding[]> {
    const findings = await defaultApiImplementation.listFindings();
    return findings.filter((f) => f.risk === "high" || f.risk === "medium");
  },

  async getFinding(findingId: string): Promise<Finding> {
    const findings = await defaultApiImplementation.listFindings();
    const match = findings.find((f) => f.id === findingId);
    if (!match) {
      throw new Error(`Finding with ID ${findingId} not found.`);
    }
    return match;
  },

  async askAi(input: AskAiInput): Promise<ChatMessage> {
    const res = await authFetch("/api/qa/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: input.question,
        conversation_id: input.conversationId,
      }),
    });
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to generate answer." }));
      throw new Error(err.detail || "Failed to generate answer.");
    }
    const data: BackendChatMessageResponse = await res.json();
    return mapChatMessage(data);
  },

  async searchProviders(
    params: ProviderSearchParams
  ): Promise<ProviderSearchResult> {
    const body: Record<string, unknown> = {
      radius_km: params.radiusKm,
    };
    if (params.location) body.location = params.location;
    if (params.latitude !== undefined && params.latitude !== null) body.latitude = params.latitude;
    if (params.longitude !== undefined && params.longitude !== null) body.longitude = params.longitude;
    if (params.specialty) body.specialty = params.specialty;
    if (params.findingId) body.finding_id = params.findingId;
    if (params.availability) body.availability = params.availability;
    if (params.kinds && params.kinds.length) body.kinds = params.kinds;

    const res = await authFetch("/api/doctor-search/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    // A place name the geocoder does not recognise, or a finding that is not
    // this patient's. Both are answers, not outages.
    if (res.status === 404) {
      throw new LocationNotFoundError(params.location || "Current Location");
    }
    // The upstream directory is down. This must stay distinct from an empty
    // result: telling a patient there are no providers near them when we simply
    // could not look would be a false statement about their area.
    if (res.status === 503) {
      const err = await res.json().catch(() => ({ detail: "" }));
      throw new ProviderDirectoryUnavailableError(err.detail || undefined);
    }
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to search for healthcare providers." }));
      throw new Error(
        typeof err.detail === "string"
          ? err.detail
          : "Failed to search for healthcare providers."
      );
    }

    return mapProviderSearch(await res.json());
  },

  async listProviderSearches(
    limit = 20
  ): Promise<ProviderSearchHistoryEntry[]> {
    const res = await authFetch(
      `/api/doctor-search/history?limit=${encodeURIComponent(String(limit))}`,
      { method: "GET" }
    );
    if (res.status === 401) return [];
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch provider search history." }));
      throw new Error(err.detail || "Failed to fetch provider search history.");
    }
    const data = await res.json();
    return (data?.searches || []).map(mapProviderHistoryEntry);
  },

  async getProviderSearch(
    searchId: string
  ): Promise<ProviderSearchResult | null> {
    const res = await authFetch(
      `/api/doctor-search/searches/${encodeURIComponent(searchId)}`,
      { method: "GET" }
    );
    if (res.status === 401) return null;
    // 404 means this patient has no such search — an expected outcome, not a
    // failure, and deliberately indistinguishable from another patient's id.
    if (res.status === 404) return null;
    if (res.status === 503) {
      const err = await res.json().catch(() => ({ detail: "" }));
      throw new ProviderDirectoryUnavailableError(err.detail || undefined);
    }
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch the provider search." }));
      throw new Error(err.detail || "Failed to fetch the provider search.");
    }
    return mapProviderSearch(await res.json());
  },

  async getProfile(): Promise<UserProfile> {
    const token = await getAccessToken();
    if (!token) {
      throw new Error("No active session found. Please sign in.");
    }
    let res = await authFetch("/api/auth/me", { method: "GET" });
    if (res.status === 401) {
      // Ensure application user is registered in PostgreSQL then retry
      try {
        await authFetch("/api/auth/register", { method: "POST" });
        res = await authFetch("/api/auth/me", { method: "GET" });
      } catch {
        // Continue to error check below
      }
    }
    if (!res.ok) {
      const err = await res
        .json()
        .catch(() => ({ detail: "Failed to fetch profile." }));
      throw new Error(err.detail || "Failed to fetch profile.");
    }
    const backendUser = await res.json();
    const sb = getSupabase();
    const {
      data: { user: sbUser },
    } = await sb.auth.getUser();

    const rawName =
      sbUser?.user_metadata?.full_name ||
      sbUser?.user_metadata?.name ||
      backendUser.email?.split("@")[0] ||
      "User";

    const legalName =
      sbUser?.user_metadata?.legal_name ||
      rawName;

    return {
      id: `MG-${String(backendUser.id).slice(0, 8).toUpperCase()}`,
      fullName: rawName,
      legalName: legalName,
      initials: getInitials(rawName),
      email: backendUser.email || sbUser?.email || "",
      phone: sbUser?.user_metadata?.phone || "—",
      dateOfBirth: sbUser?.user_metadata?.date_of_birth || "—",
      language: sbUser?.user_metadata?.language || "English",
      memberSince: formatDate(
        backendUser.created_at || sbUser?.created_at || new Date().toISOString()
      ),
      accountType: "Patient account",
    };
  },

  async updateProfile(profile: Partial<UserProfile>): Promise<UserProfile> {
    const sb = getSupabase();
    const updates: Record<string, unknown> = {};
    if (profile.fullName) updates.full_name = profile.fullName;
    if (profile.legalName) updates.legal_name = profile.legalName;
    if (profile.phone) updates.phone = profile.phone;
    if (profile.language) updates.language = profile.language;
    if (profile.dateOfBirth) updates.date_of_birth = profile.dateOfBirth;

    const { error } = await sb.auth.updateUser({
      data: updates,
    });
    if (error) {
      throw new Error(error.message);
    }
    return defaultApiImplementation.getProfile();
  },

  async changePassword(input: {
    currentPassword: string;
    newPassword: string;
  }): Promise<void> {
    const sb = getSupabase();
    const { error } = await sb.auth.updateUser({
      password: input.newPassword,
    });
    if (error) {
      throw new Error(error.message);
    }
  },

  revokeSession: unconfigured("revokeSession"),

  async exportAccountData(): Promise<Blob> {
    const docs = await defaultApiImplementation.listDocuments();
    const profile = await defaultApiImplementation.getProfile();
    const payload = JSON.stringify({ profile, documents: docs }, null, 2);
    return new Blob([payload], { type: "application/json" });
  },

  async deleteAccount(): Promise<void> {
    // Delete patient documents
    try {
      const docs = await defaultApiImplementation.listDocuments();
      for (const doc of docs) {
        await defaultApiImplementation.deleteDocument(doc.id);
      }
    } catch {
      // Continue account signout
    }
    await defaultApiImplementation.signOut();
  },
};

let activeApi: MediGuardianApi = defaultApiImplementation;

export function configureApi(implementation: Partial<MediGuardianApi>) {
  activeApi = { ...defaultApiImplementation, ...implementation };
}

export function api(): MediGuardianApi {
  return activeApi;
}

export function isApiConfigured() {
  return true;
}

export function toErrorMessage(error: unknown) {
  if (error instanceof ApiNotConfiguredError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}
