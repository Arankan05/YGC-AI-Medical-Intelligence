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
  LabResult,
  MedicalDocument,
  MedicalOverview,
  Medication,
  MedicationFlagKind,
  MedicationSafetyReport,
  Provider,
  ProviderSearchParams,
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
  listFindings(): Promise<Finding[]>;
  listAllergies(): Promise<AllergyRecord[]>;
  listAnalyses(): Promise<AIAnalysisRecord[]>;
  listNotifications(): Promise<Finding[]>;
  getFinding(findingId: string): Promise<Finding>;

  askAi(input: AskAiInput): Promise<ChatMessage>;

  searchProviders(params: ProviderSearchParams): Promise<Provider[]>;

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

function mapLabResult(item: BackendLabResultResponse): LabResult {
  const numVal = parseFloat(item.value);
  const validNum = !isNaN(numVal);
  return {
    id: String(item.id),
    name: item.test_name || "Diagnostic Test",
    unit: item.unit || "",
    referenceRange: item.reference_range || "—",
    latestValue: validNum ? numVal : 0,
    latestValueLabel: item.value || "—",
    latestDate: formatDate(item.result_date || item.created_at),
    sourceDocument: item.source_document_name || "Lab Report",
    trend: "stable",
    severity: "ok",
    statusLabel: "Recorded",
    trendLabel: "Result",
    points: [
      {
        date: formatDate(item.result_date || item.created_at),
        value: validNum ? numVal : 0,
        documentId: String(item.source_document_id || ""),
      },
    ],
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
  const confidencePct =
    typeof item.confidence === "number"
      ? Math.round(item.confidence <= 1 ? item.confidence * 100 : item.confidence)
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
    // Sync application User & Patient records in PostgreSQL
    try {
      await authFetch("/api/auth/register", { method: "POST" });
    } catch {
      // Non-fatal if already registered
    }
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

  askAi: (input: AskAiInput) => unconfigured("askAi")(input),
  searchProviders: (params: ProviderSearchParams) =>
    unconfigured("searchProviders")(params),

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
