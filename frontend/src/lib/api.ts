/**
 * Backend integration points.
 *
 * The frontend is deliberately backend-agnostic: every server-dependent action
 * the UI can trigger is declared here as a typed operation. Nothing in this file
 * calls a real endpoint — no API surface is assumed or invented. When the
 * backend lands, implement `MediGuardianApi` once (REST, Supabase, RPC, …) and
 * pass it to `configureApi()` from a client bootstrap; every screen picks it up
 * without further changes.
 *
 * Until then each operation rejects with `ApiNotConfiguredError`, which the UI
 * surfaces as an inline error state instead of failing silently.
 */

import type {
  ChatMessage,
  CrossCheckIssue,
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
    super(
      `"${operation}" is not connected to a backend yet. Wire it up via configureApi().`
    );
    this.name = "ApiNotConfiguredError";
  }
}

export interface SignInInput {
  email: string;
  password: string;
  keepSignedIn: boolean;
}

export interface SignUpInput {
  fullName: string;
  email: string;
  password: string;
  acknowledgedDisclaimer: boolean;
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

const OPERATIONS: (keyof MediGuardianApi)[] = [
  "signIn",
  "signUp",
  "signOut",
  "listDocuments",
  "uploadDocument",
  "deleteDocument",
  "retryDocument",
  "listTimeline",
  "listMedications",
  "listCrossCheckIssues",
  "listLabResults",
  "listFindings",
  "getFinding",
  "askAi",
  "searchProviders",
  "getProfile",
  "updateProfile",
  "changePassword",
  "revokeSession",
  "exportAccountData",
  "deleteAccount",
];

const notConfiguredApi = Object.fromEntries(
  OPERATIONS.map((operation) => [operation, unconfigured(operation)])
) as unknown as MediGuardianApi;

let activeApi: MediGuardianApi = notConfiguredApi;

/** Swap in the real implementation once the backend exists. */
export function configureApi(implementation: Partial<MediGuardianApi>) {
  activeApi = { ...notConfiguredApi, ...implementation };
}

export function api(): MediGuardianApi {
  return activeApi;
}

/** True while no backend implementation has been registered. */
export function isApiConfigured() {
  return activeApi !== notConfiguredApi;
}

/** Normalises any thrown value into a message the UI can display. */
export function toErrorMessage(error: unknown) {
  if (error instanceof ApiNotConfiguredError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}
