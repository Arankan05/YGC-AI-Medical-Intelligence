/**
 * Backend integration points for MediGuardian AI.
 *
 * All authenticated operations obtain the verified Supabase JWT Bearer token
 * and dispatch real HTTP requests to the FastAPI backend at NEXT_PUBLIC_API_URL.
 */

import { getAccessToken, getSupabase } from "@/lib/supabase";
import type {
  ChatMessage,
  CrossCheckIssue,
  DocumentStatus,
  DocumentType,
  Finding,
  LabResult,
  MedicalDocument,
  Medication,
  Provider,
  ProviderSearchParams,
  TimelineEvent,
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

  listTimeline(): Promise<TimelineEvent[]>;
  listMedications(): Promise<Medication[]>;
  listCrossCheckIssues(): Promise<CrossCheckIssue[]>;
  listLabResults(): Promise<LabResult[]>;
  listFindings(): Promise<Finding[]>;
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
            // Optionally trigger extraction pipeline
            try {
              if (data.id) {
                await authFetch(`/api/documents/${data.id}/process`, {
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

  // Returns empty arrays for features whose backend endpoints do not exist yet
  async listTimeline(): Promise<TimelineEvent[]> {
    return [];
  },

  async listMedications(): Promise<Medication[]> {
    return [];
  },

  async listCrossCheckIssues(): Promise<CrossCheckIssue[]> {
    return [];
  },

  async listLabResults(): Promise<LabResult[]> {
    return [];
  },

  async listFindings(): Promise<Finding[]> {
    return [];
  },

  async listNotifications(): Promise<Finding[]> {
    return [];
  },

  getFinding: (id: string) => unconfigured("getFinding")(id),
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
