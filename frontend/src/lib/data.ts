/**
 * Application Constants and UI Metadata for MediGuardian AI.
 * 
 * Contains UI configuration, pipeline descriptions, security explanations, and
 * empty default arrays for real-user data flow.
 *
 * Provider records are never held here. Every healthcare provider shown comes
 * from the backend, which sources it from OpenStreetMap at request time.
 */

import type {
  ChatMessage,
  CrossCheckIssue,
  DashboardMetric,
  Finding,
  LabResult,
  MedicalDocument,
  Medication,
  PipelineStep,
  TimelineEvent,
  UploadItem,
} from "@/lib/types";

export const documents: MedicalDocument[] = [];
export const timelineEvents: TimelineEvent[] = [];
export const medications: Medication[] = [];
export const crossCheckIssues: CrossCheckIssue[] = [];
export const labResults: LabResult[] = [];
export const findings: Finding[] = [];
export const notificationFindings: Finding[] = [];
export const chatHistory: ChatMessage[] = [];
export const safetyChatHistory: ChatMessage[] = [];
export const demoUploadItems: UploadItem[] = [];

export const emptyStateMetrics: DashboardMetric[] = [
  {
    id: "documents",
    kind: "documents",
    label: "MEDICAL DOCUMENTS",
    value: "0",
    delta: "Nothing uploaded",
  },
  {
    id: "events",
    kind: "events",
    label: "MEDICAL EVENTS",
    value: "0",
    delta: "Nothing extracted",
  },
  {
    id: "medications",
    kind: "medications",
    label: "ACTIVE MEDICATIONS",
    value: "0",
    delta: "Nothing to check",
  },
  {
    id: "findings",
    kind: "findings",
    label: "AI FINDINGS",
    value: "0",
    delta: "Nothing analysed",
  },
  {
    id: "priority",
    kind: "priority",
    label: "PRIORITY ITEMS",
    value: "0",
    delta: "Nothing flagged",
  },
];

export const gettingStartedSteps = [
  {
    step: "STEP 1",
    title: "Upload your existing medical documents",
    description:
      "Prescriptions, lab reports, discharge summaries or doctor’s notes. Multiple formats supported (PDF, JPG, PNG up to 20 MB).",
    icon: "upload" as const,
  },
  {
    step: "STEP 2",
    title: "Automatic AI extraction & cross-check",
    description:
      "MediGuardian reads the text, structures medications and lab values, and compares them against your other records.",
    icon: "activity" as const,
  },
  {
    step: "STEP 3",
    title: "View contradiction findings & trends",
    description:
      "Review potential allergy conflicts, duplicate dosages, and biomarker trends across visits — with evidence linked back to source files.",
    icon: "alert" as const,
  },
];

export const uploadPipelineSteps: PipelineStep[] = [
  {
    id: "validate",
    title: "Validate",
    description: "Format, size and readability checks",
    status: "pending",
  },
  {
    id: "store",
    title: "Store",
    description: "Encrypted private cloud storage",
    status: "pending",
  },
  {
    id: "extract",
    title: "Extract text",
    description: "PyMuPDF text layer / Tesseract OCR",
    status: "pending",
  },
  {
    id: "ai-extraction",
    title: "AI extraction",
    description: "Medications, labs, diagnoses, dates",
    status: "pending",
  },
  {
    id: "cross-check",
    title: "Cross-check",
    description: "Compare against your other records",
    status: "pending",
  },
];

export const askAiSuggestions = [
  "Which medications am I taking now?",
  "Any results out of range?",
  "What did the discharge summary say?",
];

export const answerPipeline = [
  {
    title: "Question processing",
    description: "Your question is embedded and normalised.",
  },
  {
    title: "Vector search",
    description:
      "pgvector retrieves the passages most similar to your question from your own documents.",
  },
  {
    title: "Medical events",
    description:
      "Matching structured records — medications, lab results, allergies — are pulled from the database.",
  },
  {
    title: "Timeline context",
    description:
      "Retrieved items are ordered by medical date so the model sees what happened when.",
  },
  {
    title: "Answer + evidence",
    description:
      "The model answers only from retrieved context, and every claim is linked back to its source.",
  },
];

export const safetyRules = [
  {
    title: "Never diagnoses",
    description:
      "The system states potential findings, never a condition or disease name.",
  },
  {
    title: "Never invents",
    description:
      "If the records do not contain the answer, it says the evidence is insufficient.",
  },
  {
    title: "Never prescribes",
    description: "It does not tell you to start, stop or change any medication.",
  },
  {
    title: "Always attributes",
    description:
      "Every statement links back to the document and page it came from.",
  },
  {
    title: "Always redirects",
    description:
      "High-risk and low-confidence findings route you to a real professional.",
  },
];

export const askAiScopeNote =
  "Ask AI answers only from documents you have uploaded. It will not answer general medical questions, and it will not give a diagnosis. If your records do not contain enough information, it says so instead of guessing.";

export const providerSearchSteps = [
  {
    title: "Specialty matching",
    description: "The finding category maps to a professional type.",
  },
  {
    title: "Nominatim geocoding",
    description: "Your place name becomes latitude and longitude.",
  },
  {
    title: "Overpass query",
    description:
      "OpenStreetMap is queried for healthcare facilities within the radius.",
  },
  {
    title: "Distance calculation",
    description: "Straight-line distance from your coordinates, computed in code.",
  },
  {
    title: "Transparent ranking",
    description:
      "Specialty relevance 40%, distance 30%, data completeness 15%, other verified details 15%.",
  },
];

export const providerAttribution = {
  overline: "REAL PROVIDER DATA ONLY",
  body: "Every provider shown comes from OpenStreetMap via the Overpass API. No doctors, clinics, addresses, phone numbers, ratings or appointment slots are ever generated by this system. Where a field is missing from the source data, it is shown as “Not available”.",
  credit: "© OpenStreetMap contributors · Nominatim usage policy respected",
};

export const availabilityOptions = [
  { value: "this-week", label: "This week", hint: "Next 7 days" },
  { value: "evenings", label: "Evenings", hint: "After 5pm" },
  { value: "weekends", label: "Weekends", hint: "Sat & Sun" },
  { value: "flexible", label: "Flexible", hint: "Any time" },
];

export const radiusOptions = [5, 10, 25, 50];

export const providerSearchDefaults = {
  // Left blank on purpose: prefilling a place would search somewhere the
  // patient never chose.
  location: "",
  geocodeNote:
    "Resolved via Nominatim. The place you search for is saved to your provider-search history, which is stored separately from your medical records.",
  availability: "evenings",
  radiusKm: 10,
  availabilityNote:
    "Availability is treated as a preference for ranking. MediGuardian never invents appointment times — only opening hours published in OpenStreetMap are shown, and providers without published hours are labelled “Not available”.",
  suitableProfessional: {
    title: "General Practitioner / Specialist Doctor",
    rationale:
      "Consult a qualified healthcare provider or clinic near you to review your medical health and records.",
  },
};

export const providerResultsNote =
  "Ranking weights: Specialty relevance (40%) · Distance (30%) · Data completeness (15%) · Verified details (15%). OpenStreetMap data only.";

export const providerRankingWeights =
  "Specialty (40%) · Distance (30%) · Completeness (15%) · Verified (15%)";

export const providerEmptyState = {
  headline: "No providers found in this area",
  body: "No healthcare facilities were returned within your search radius. Try expanding the search radius or searching for a neighbouring town.",
  searchLog: [
    { label: "AREA SEARCHED", value: "Selected location within radius" },
    { label: "SOURCE DATA", value: "OpenStreetMap healthcare database" },
    { label: "SPECIALTY FILTERS", value: "Medical clinics and pharmacies" },
  ],
  reassurance: "We never invent placeholder clinics or doctors when local data is not available.",
};

export const providerErrorState = {
  headline: "Healthcare directory temporarily unavailable",
  body: "We could not reach OpenStreetMap / Overpass to retrieve healthcare facilities in this area. You can retry the search or check back shortly.",
  technical: [
    { label: "ENDPOINT", value: "Overpass API / Nominatim geocoder" },
    { label: "STATUS", value: "Service unreachable or timed out" },
  ],
  reassurance: "Your medical documents and search queries remain completely private.",
};

export const securityToggles = [
  {
    id: "encryption",
    title: "Zero-knowledge encryption for uploaded files",
    description:
      "Files are encrypted with AES-256 before writing to storage. Only your account session holds the decryption key.",
    enabled: true,
  },
  {
    id: "training-opt-out",
    title: "Exclude records from model training",
    description:
      "Your documents are never used to train or fine-tune AI models. This cannot be disabled.",
    enabled: true,
  },
  {
    id: "audit-logging",
    title: "Audit logging for document access",
    description:
      "Every view, extraction and AI prompt generates an immutable log entry visible in your audit trail.",
    enabled: true,
  },
];

export const isolationNotes = [
  {
    title: "PostgreSQL row-level security",
    description:
      "Every database query includes `WHERE patient_id = :id`. The database engine itself enforces that one user cannot read or update another user's rows.",
  },
  {
    title: "Isolated vector namespaces",
    description:
      "Vector embeddings are namespaced per user. Similarity searches only query chunks with your patient ID.",
  },
  {
    title: "Private Supabase storage",
    description:
      "Storage bucket paths are prefixed with your unique UUID. Signed URLs expire after one hour and are never shared.",
  },
];

export const deleteDataNote =
  "Permanently deletes all uploaded documents, extracted medical records, lab trends, and contradiction findings. This action cannot be undone.";

export const dataActions = [
  {
    id: "export",
    title: "Export all records (JSON)",
    description:
      "Download a full archive of your documents, extracted entities, and finding reports.",
  },
  {
    id: "audit",
    title: "View access audit log",
    description:
      "Review the timestamp, IP address, and scope of every access to your medical records.",
  },
];
