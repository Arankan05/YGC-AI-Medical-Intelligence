/**
 * Screen content transcribed from the MediGuardian AI Figma file.
 *
 * This is presentation data only — it exists so every screen renders exactly as
 * designed while the backend is built. Replace these exports with data returned
 * from `src/lib/api.ts` once the API is wired; the types are identical.
 */

import type {
  ChatMessage,
  CrossCheckIssue,
  DashboardMetric,
  Finding,
  LabResult,
  MedicalDocument,
  Medication,
  MedicationFlagKind,
  RiskLevel,
  PipelineStep,
  UploadItem,
  Provider,
  SecuritySession,
  TimelineEvent,
  UserProfile,
} from "@/lib/types";

/** Figma: user-card in the App Sidebar (12:72) and 18 · Profile & Security (38:1472). */
export const currentUser: UserProfile = {
  id: "MG-2026-004182",
  fullName: "R. Perera",
  legalName: "Ravindu Perera",
  initials: "RP",
  email: "r.perera@example.lk",
  phone: "+94 77 412 0093",
  dateOfBirth: "14 August 1981",
  language: "English",
  memberSince: "January 2026",
  accountType: "Patient account",
};

/**
 * Record totals as written in the Figma copy. The tables and lists below render
 * a representative page of each set, so header counts come from here rather
 * than from `array.length`.
 */
export const recordTotals = {
  documents: 12,
  providers: 4,
  visits: 6,
  events: 27,
  activeMedications: 5,
  discontinuedMedications: 2,
  labResults: 18,
  labReports: 3,
  trendedTests: 4,
  findings: 5,
  findingsByRisk: { high: 2, medium: 2, low: 1 },
};

export const emptyStateMetrics: DashboardMetric[] = [
  {
    id: "documents",
    kind: "documents",
    label: "MEDICAL DOCUMENTS",
    value: "—",
    delta: "Nothing uploaded",
  },
  {
    id: "events",
    kind: "events",
    label: "MEDICAL EVENTS",
    value: "—",
    delta: "Nothing extracted",
  },
  {
    id: "medications",
    kind: "medications",
    label: "ACTIVE MEDICATIONS",
    value: "—",
    delta: "Nothing to check",
  },
  {
    id: "findings",
    kind: "findings",
    label: "AI FINDINGS",
    value: "—",
    delta: "Nothing analysed",
  },
  {
    id: "priority",
    kind: "priority",
    label: "PRIORITY ITEMS",
    value: "—",
    delta: "Nothing flagged",
  },
];

export const gettingStartedSteps = [
  {
    step: "STEP 1",
    icon: "upload" as const,
    title: "Upload what you already have",
    description:
      "PDFs and photos of prescriptions, lab reports, scans and discharge summaries. Scanned images are read with OCR.",
  },
  {
    step: "STEP 2",
    icon: "activity" as const,
    title: "We structure and connect them",
    description:
      "Medications, lab values, diagnoses and dates are extracted, then placed on one timeline across every provider.",
  },
  {
    step: "STEP 3",
    icon: "alert" as const,
    title: "Review what does not line up",
    description:
      "Interactions, duplicates, dosage conflicts and allergy contradictions — each shown with the document it came from.",
  },
];

/** Figma: 04 · Documents — documents-table (node 23:505). */
export const documents: MedicalDocument[] = [
  {
    id: "doc-1",
    title: "Prescription_June.pdf",
    type: "Prescription",
    provider: "Nawaloka Hospital",
    documentDate: "12 Jun 2026",
    uploadedAt: "2 hours ago",
    pages: 2,
    sizeLabel: "PDF · 2 pages",
    status: "completed",
    source: "digital",
    extractedItems: 6,
  },
  {
    id: "doc-2",
    title: "Doctor_Note_March.pdf",
    type: "Doctor Note",
    provider: "Dr. S. Fernando",
    documentDate: "12 Mar 2026",
    uploadedAt: "3 days ago",
    pages: 1,
    sizeLabel: "PDF · 1 page",
    status: "completed",
    source: "digital",
    extractedItems: 4,
  },
  {
    id: "doc-3",
    title: "Lab_Report_March.pdf",
    type: "Lab Report",
    provider: "Asiri Laboratories",
    documentDate: "12 Mar 2026",
    uploadedAt: "3 days ago",
    pages: 3,
    sizeLabel: "PDF · 3 pages",
    status: "completed",
    source: "digital",
    extractedItems: 11,
  },
  {
    id: "doc-4",
    title: "Discharge_Summary_Feb.pdf",
    type: "Discharge Summary",
    provider: "Nawaloka Hospital",
    documentDate: "02 Feb 2026",
    uploadedAt: "3 days ago",
    pages: 4,
    sizeLabel: "PDF · 4 pages",
    status: "completed",
    source: "digital",
    extractedItems: 9,
  },
  {
    id: "doc-5",
    title: "Scanned_Prescription_Jan.jpg",
    type: "Prescription",
    provider: "Dr. M. Silva",
    documentDate: "12 Jan 2026",
    uploadedAt: "Just now",
    pages: 1,
    sizeLabel: "Image · OCR",
    status: "extracting",
    source: "scanned",
  },
  {
    id: "doc-6",
    title: "Blood_Report_January.pdf",
    type: "Lab Report",
    provider: "Asiri Laboratories",
    documentDate: "12 Jan 2026",
    uploadedAt: "12 Jan 2026",
    pages: 2,
    sizeLabel: "PDF · 2 pages",
    status: "analyzing",
    source: "digital",
  },
  {
    id: "doc-7",
    title: "Xray_Report_2025.tiff",
    type: "Imaging Report",
    provider: "—",
    documentDate: "—",
    uploadedAt: "12 Jan 2026",
    pages: 0,
    sizeLabel: "Unsupported type",
    status: "failed",
    source: "scanned",
  },
];
/** Figma: 06 · Patient Timeline — panel · timeline (node 25:512). */
export const timelineEvents: TimelineEvent[] = [
  {
    id: "event-1",
    date: "12 Jun 2026",
    kind: "prescription",
    title: "Prescription issued · City Medical Centre",
    provider: "City Medical Centre",
    summary:
      "Amoxicillin 500 mg three times daily · Aspirin 75 mg once daily. Prescriber: Dr S. Jayasuriya.",
    documentTitle: "Prescription_June.pdf",
    documentId: "doc-1",
    tags: ["2 findings raised"],
    risk: "high",
  },
  {
    id: "event-2",
    date: "12 Mar 2026",
    kind: "note",
    title: "Doctor's note · Lakeside Clinic",
    provider: "Lakeside Clinic",
    summary:
      "Allergy recorded — Penicillin, presenting as rash. Patient advised to avoid penicillin-class antibiotics.",
    documentTitle: "Doctor_Note_March.pdf",
    documentId: "doc-2",
    tags: ["Allergy recorded"],
    risk: "medium",
  },
  {
    id: "event-3",
    date: "12 Mar 2026",
    kind: "lab",
    title: "Lab report · Lakeside Clinic",
    provider: "Lakeside Clinic",
    summary:
      "Haemoglobin 12.1 g/dL (below 13.0–17.0 range) · Creatinine 1.0 mg/dL · HbA1c 7.4%.",
    documentTitle: "Lab_Report_March.pdf",
    documentId: "doc-3",
    tags: ["Below range"],
    risk: "medium",
  },
  {
    id: "event-4",
    date: "02 Feb 2026",
    kind: "visit",
    title: "Discharge summary · General Hospital",
    provider: "General Hospital",
    summary:
      "Two-night admission for observation. No change to existing medications on discharge.",
    documentTitle: "Discharge_Summary_Feb.pdf",
    documentId: "doc-4",
    tags: [],
  },
  {
    id: "event-5",
    date: "12 Jan 2026",
    kind: "lab",
    title: "Lab report · General Hospital",
    provider: "General Hospital",
    summary:
      "Haemoglobin 13.5 g/dL (within range) · HbA1c 7.2% · Platelets 240 ×10⁹/L.",
    documentTitle: "Blood_Report_January.pdf",
    documentId: "doc-6",
    tags: [],
  },
  {
    id: "event-6",
    date: "12 Jan 2026",
    kind: "prescription",
    title: "Prescription issued · General Hospital",
    provider: "General Hospital",
    summary:
      "Warfarin 5 mg once daily · Metformin 500 mg twice daily. Prescriber: Dr N. Wickrama.",
    documentTitle: "Prescription_January.pdf",
    documentId: "doc-5",
    tags: [],
  },
];

export const timelineRange = "Jan 2026 – Jun 2026";
/** Figma: 08 · Medications & Cross-Check — medication-table (node 26:633). */
export const medications: Medication[] = [
  {
    id: "med-1",
    name: "Warfarin",
    genericName: "Anticoagulant",
    dosage: "5 mg",
    frequency: "Once daily",
    startedOn: "12 Jan 2026",
    prescribedBy: "Dr N. Wickrama",
    sourceDocumentId: "Prescription_January.pdf",
    status: "active",
    flags: ["interaction"],
  },
  {
    id: "med-2",
    name: "Aspirin",
    genericName: "Antiplatelet",
    dosage: "75 mg",
    frequency: "Once daily",
    startedOn: "12 Jun 2026",
    prescribedBy: "Dr S. Jayasuriya",
    sourceDocumentId: "Prescription_June.pdf",
    status: "active",
    flags: ["interaction"],
  },
  {
    id: "med-3",
    name: "Amoxicillin",
    genericName: "Penicillin-class antibiotic",
    dosage: "500 mg",
    frequency: "Three times daily",
    startedOn: "12 Jun 2026",
    prescribedBy: "Dr S. Jayasuriya",
    sourceDocumentId: "Prescription_June.pdf",
    status: "active",
    flags: ["allergy"],
  },
  {
    id: "med-4",
    name: "Metformin",
    genericName: "Antidiabetic",
    dosage: "500 mg",
    frequency: "Twice daily",
    startedOn: "12 Jan 2026",
    prescribedBy: "Dr N. Wickrama",
    sourceDocumentId: "Prescription_January.pdf",
    status: "active",
    flags: ["duplicate"],
  },
  {
    id: "med-5",
    name: "Metformin",
    genericName: "Antidiabetic",
    dosage: "500 mg",
    frequency: "Three times daily",
    startedOn: "12 Jun 2026",
    prescribedBy: "Dr S. Jayasuriya",
    sourceDocumentId: "Prescription_June.pdf",
    status: "active",
    flags: ["duplicate", "dosage"],
  },
  {
    id: "med-6",
    name: "Atorvastatin",
    genericName: "Statin",
    dosage: "20 mg",
    frequency: "Once at night",
    startedOn: "18 Mar 2026",
    prescribedBy: "Dr S. Fernando",
    sourceDocumentId: "Prescription_March.pdf",
    status: "active",
    flags: [],
  },
  {
    id: "med-7",
    name: "Cetirizine",
    genericName: "Antihistamine · discontinued",
    dosage: "10 mg",
    frequency: "Once daily",
    startedOn: "02 Feb 2026",
    prescribedBy: "General Hospital",
    sourceDocumentId: "Discharge_Summary_Feb.pdf",
    status: "stopped",
    flags: [],
  },
];

/** Figma: 08 · cross-check-summary (node 26:594). */
export const crossCheckSummary: {
  id: MedicationFlagKind;
  label: string;
  count: number;
  detail: string;
  risk: RiskLevel;
}[] = [
  {
    id: "interaction",
    label: "DRUG INTERACTIONS",
    count: 1,
    detail: "Warfarin + Aspirin",
    risk: "high",
  },
  {
    id: "allergy",
    label: "ALLERGY CONTRADICTIONS",
    count: 1,
    detail: "Amoxicillin vs penicillin allergy",
    risk: "high",
  },
  {
    id: "duplicate",
    label: "DUPLICATE PRESCRIPTIONS",
    count: 1,
    detail: "Metformin on two prescriptions",
    risk: "medium",
  },
  {
    id: "dosage",
    label: "DOSAGE CONFLICTS",
    count: 1,
    detail: "Metformin 2×/day vs 3×/day",
    risk: "medium",
  },
];

export const crossCheckIssues: CrossCheckIssue[] = [];
/** Figma: 09 · Lab Results & Trends — trend-cards (27:682) and results-table (27:747). */
export const labResults: LabResult[] = [
  {
    id: "haemoglobin",
    name: "Haemoglobin",
    unit: "g/dL",
    referenceRange: "13.0 – 17.0",
    referenceLow: 13,
    referenceHigh: 17,
    latestValue: 10.8,
    latestValueLabel: "10.8",
    latestDate: "12 Jun 2026",
    sourceDocument: "Lab_Report_June.pdf",
    trend: "falling",
    severity: "high",
    statusLabel: "Below range",
    trendLabel: "Declining · 3 tests",
    points: [
      { date: "Jan 2026", value: 13.5, documentId: "doc-6" },
      { date: "Mar 2026", value: 12.1, documentId: "doc-3" },
      { date: "Jun 2026", value: 10.8, documentId: "doc-1" },
    ],
  },
  {
    id: "hba1c",
    name: "HbA1c",
    unit: "%",
    referenceRange: "4.0 – 5.6",
    referenceLow: 4,
    referenceHigh: 5.6,
    latestValue: 7.6,
    latestValueLabel: "7.6",
    latestDate: "12 Jun 2026",
    sourceDocument: "Lab_Report_June.pdf",
    trend: "rising",
    severity: "medium",
    statusLabel: "Above range",
    trendLabel: "Rising · 3 tests",
    points: [
      { date: "Jan 2026", value: 7.2, documentId: "doc-6" },
      { date: "Mar 2026", value: 7.4, documentId: "doc-3" },
      { date: "Jun 2026", value: 7.6, documentId: "doc-1" },
    ],
  },
  {
    id: "creatinine",
    name: "Creatinine",
    unit: "mg/dL",
    referenceRange: "0.7 – 1.3",
    referenceLow: 0.7,
    referenceHigh: 1.3,
    latestValue: 1.0,
    latestValueLabel: "1.0",
    latestDate: "12 Mar 2026",
    sourceDocument: "Lab_Report_March.pdf",
    trend: "stable",
    severity: "ok",
    statusLabel: "Normal",
    trendLabel: "Stable · 3 tests",
    points: [
      { date: "Nov 2025", value: 0.98, documentId: "doc-6" },
      { date: "Jan 2026", value: 1.02, documentId: "doc-6" },
      { date: "Mar 2026", value: 1.0, documentId: "doc-3" },
    ],
  },
  {
    id: "platelets",
    name: "Platelets",
    unit: "×10⁹/L",
    referenceRange: "150 – 400",
    referenceLow: 150,
    referenceHigh: 400,
    latestValue: 240,
    latestValueLabel: "240",
    latestDate: "12 Jan 2026",
    sourceDocument: "Blood_Report_January.pdf",
    trend: "stable",
    severity: "ok",
    statusLabel: "Normal",
    trendLabel: "Stable · 2 tests",
    points: [
      { date: "Nov 2025", value: 236, documentId: "doc-6" },
      { date: "Jan 2026", value: 240, documentId: "doc-6" },
    ],
  },
  {
    id: "fasting-glucose",
    name: "Fasting glucose",
    unit: "mg/dL",
    referenceRange: "70 – 99",
    referenceLow: 70,
    referenceHigh: 99,
    latestValue: 132,
    latestValueLabel: "132",
    latestDate: "12 Jun 2026",
    sourceDocument: "Lab_Report_June.pdf",
    trend: "rising",
    severity: "medium",
    statusLabel: "Above range",
    trendLabel: "1 test",
    points: [{ date: "Jun 2026", value: 132, documentId: "doc-1" }],
  },
  {
    id: "total-cholesterol",
    name: "Total cholesterol",
    unit: "mg/dL",
    referenceRange: "Below 200",
    referenceHigh: 200,
    latestValue: 214,
    latestValueLabel: "214",
    latestDate: "18 Mar 2026",
    sourceDocument: "Lab_Report_March.pdf",
    trend: "stable",
    severity: "medium",
    statusLabel: "Above range",
    trendLabel: "1 test",
    points: [{ date: "Mar 2026", value: 214, documentId: "doc-3" }],
  },
];

/** Figma: 09 · AI EXPLANATION OF TRENDS (node 27:889). */
export const labTrendExplanation =
  "Across three lab reports spanning five months, haemoglobin fell from 13.5 to 10.8 g/dL and now sits below the reference range, while HbA1c and fasting glucose both moved upward. Reference ranges and directional comparisons are calculated in code; the wording above is generated from those calculated results. These are potential findings from your own records, not a diagnosis — please discuss them with a qualified healthcare professional.";
/**
 * Figma: 10 · AI Findings — findings-list (node 28:772);
 * the detail fields come from 11 · Finding Detail (nodes 29:849, 29:871).
 */
export const findings: Finding[] = [
  {
    id: "allergy-contradiction",
    title: "Potential allergy contradiction",
    category: "allergy",
    categoryLabel: "ALLERGY CHECK",
    categoryName: "Allergy / contradiction",
    risk: "high",
    confidence: 94,
    summary:
      "A penicillin allergy is recorded in your March doctor’s note, and a penicillin-class antibiotic appears on the prescription issued on 12 June. This is a potential contradiction between two of your own records — not a confirmed reaction.",
    detectedOn: "12 Jun 2026",
    detectedAt: "12 Jun 2026, 09:41",
    documentsInvolved: "2 of 12",
    reviewStatus: "Awaiting your review",
    guidance: "Prompt consultation recommended",
    relatedMedications: ["Amoxicillin"],
    evidence: [
      {
        id: "ev-1",
        documentId: "doc-2",
        documentTitle: "Doctor_Note_March.pdf",
        page: 1,
        quote:
          "“Allergy: Penicillin — presenting as rash. Patient advised to avoid penicillin-class antibiotics.”",
        recordedOn: "12 Mar 2026 · Lakeside Clinic",
        tone: "medium",
      },
      {
        id: "ev-2",
        documentId: "doc-1",
        documentTitle: "Prescription_June.pdf",
        page: 1,
        quote:
          "“Amoxicillin 500 mg — three times daily for 7 days. Prescriber: Dr S. Jayasuriya.”",
        recordedOn: "12 Jun 2026 · City Medical Centre",
        tone: "high",
      },
    ],
    whatThisMeans:
      "Your doctor’s note from 12 March 2026 records an allergy to penicillin, presenting as a rash, with advice to avoid penicillin-class antibiotics. The prescription issued on 12 June 2026 by a different provider includes amoxicillin, which belongs to that same class. MediGuardian cannot tell whether the prescriber was aware of this allergy or reassessed it — only that two of your own records point in opposite directions, and that this is worth confirming before your next dose.",
    determination: [
      {
        kind: "deterministic",
        text: "Allergy records and active prescriptions were matched by normalised drug name and drug class in backend code.",
      },
      {
        kind: "deterministic",
        text: "Dates were compared: the allergy record (12 Mar) precedes the prescription (12 Jun), and no later record retracts it.",
      },
      {
        kind: "ai",
        text: "The language model read both extracts in context and confirmed they refer to the same drug class.",
      },
    ],
    contributingFactors: [
      "Exact drug-class match between allergy record and prescription",
      "Both extracts came from selectable PDF text, not OCR",
      "No later record retracts or reassesses the allergy",
    ],
    recommendedAction:
      "Do not stop or change any medication on your own. Confirm with the prescribing doctor or a pharmacist whether this antibiotic is appropriate given the allergy recorded in March.",
    suitableProfessional: {
      title: "Prescribing Doctor / Pharmacist",
      rationale:
        "Matched from the finding category: allergy contradictions route to the prescriber or a pharmacist rather than a specialist.",
    },
    providerCta: { label: "Find a doctor or pharmacist", primary: true },
  },
  {
    id: "medication-interaction",
    title: "Potential medication interaction",
    category: "interaction",
    categoryLabel: "INTERACTION CHECK",
    categoryName: "Interaction / bleeding risk",
    risk: "high",
    confidence: 91,
    summary:
      "Two medications that can both affect bleeding risk appear as active at the same time, prescribed at different visits by different providers. Neither prescription references the other.",
    detectedOn: "12 Jun 2026",
    detectedAt: "12 Jun 2026, 09:41",
    documentsInvolved: "2 of 12",
    reviewStatus: "Awaiting your review",
    guidance: "Prompt consultation recommended",
    relatedMedications: ["Warfarin", "Aspirin"],
    evidence: [
      {
        id: "ev-3",
        documentId: "doc-5",
        documentTitle: "Prescription_January.pdf",
        page: 1,
        quote: "“Warfarin 5 mg — once daily, ongoing.”",
        recordedOn: "12 Jan 2026 · General Hospital",
        tone: "medium",
      },
      {
        id: "ev-4",
        documentId: "doc-1",
        documentTitle: "Prescription_June.pdf",
        page: 1,
        quote: "“Aspirin 75 mg — once daily.”",
        recordedOn: "12 Jun 2026 · City Medical Centre",
        tone: "high",
      },
    ],
    whatThisMeans:
      "Warfarin was prescribed as ongoing in January and aspirin was added in June by a different provider. Both can affect bleeding risk, and neither prescription references the other. MediGuardian cannot tell whether this combination was intended — only that both appear active at the same time in your own records.",
    determination: [
      {
        kind: "deterministic",
        text: "Active medication periods were compared by start date and stop date across every prescription.",
      },
      {
        kind: "deterministic",
        text: "Both medications were matched against a known interaction pair by normalised drug name.",
      },
      {
        kind: "ai",
        text: "The language model confirmed both extracts describe currently active, ongoing instructions.",
      },
    ],
    contributingFactors: [
      "Both medications are recorded as active with no stop date",
      "The prescriptions come from two different providers",
      "Both extracts came from selectable PDF text, not OCR",
    ],
    recommendedAction:
      "Do not stop or change any medication on your own. Ask the prescribing doctor or a pharmacist whether taking both together is intended in your case.",
    suitableProfessional: {
      title: "Prescribing Doctor / Pharmacist",
      rationale:
        "Matched from the finding category: interaction checks route to the prescriber or a pharmacist rather than a specialist.",
    },
    providerCta: { label: "Find a doctor or pharmacist", primary: true },
  },
  {
    id: "duplicate-dosage-conflict",
    title: "Potential duplicate and dosage conflict",
    category: "dosage",
    categoryLabel: "DOSAGE CHECK",
    categoryName: "Duplicate / dosage conflict",
    risk: "medium",
    confidence: 86,
    summary:
      "The same medication appears on two prescriptions with different frequencies and no recorded stop date in between, so it is unclear which instruction is currently in effect.",
    detectedOn: "12 Jun 2026",
    detectedAt: "12 Jun 2026, 09:41",
    documentsInvolved: "2 of 12",
    reviewStatus: "Awaiting your review",
    guidance: "Worth raising with a healthcare professional",
    relatedMedications: ["Metformin"],
    evidence: [
      {
        id: "ev-5",
        documentId: "doc-5",
        documentTitle: "Prescription_January.pdf",
        page: 1,
        quote: "“Metformin 500 mg — twice daily.”",
        recordedOn: "12 Jan 2026 · General Hospital",
        tone: "medium",
      },
      {
        id: "ev-6",
        documentId: "doc-1",
        documentTitle: "Prescription_June.pdf",
        page: 1,
        quote: "“Metformin 500 mg — three times daily.”",
        recordedOn: "12 Jun 2026 · City Medical Centre",
        tone: "medium",
      },
    ],
    whatThisMeans:
      "Metformin 500 mg appears on the January prescription at twice daily and on the June prescription at three times daily. No record between the two stops the earlier instruction, so both remain open in your records and the current intended frequency is ambiguous.",
    determination: [
      {
        kind: "deterministic",
        text: "Prescriptions were grouped by normalised drug name and strength to detect repeats.",
      },
      {
        kind: "deterministic",
        text: "Frequencies were compared numerically and no stop date was found between the two prescriptions.",
      },
      {
        kind: "ai",
        text: "The language model confirmed both extracts describe the same medication rather than a taper.",
      },
    ],
    contributingFactors: [
      "Identical drug name and strength on both prescriptions",
      "No stop or review date recorded between them",
      "Different prescribers at different visits",
    ],
    recommendedAction:
      "Confirm with a pharmacist or your prescribing doctor which frequency you should be following now, and ask for the older instruction to be closed off in your records.",
    suitableProfessional: {
      title: "Pharmacist",
      rationale:
        "Matched from the finding category: duplicate and dosage questions are usually resolved fastest by a pharmacist.",
    },
    providerCta: { label: "Find a pharmacist", primary: false },
  },
];

/** High-risk findings shown in the top-bar notification popover. */
export const notificationFindings: Finding[] = findings.filter(
  (finding) => finding.risk === "high"
);

export const findingsSortLabel = "Sorted by risk, then confidence";
/** Figma: 07 · Dashboard — metric-row (node 19:156). */
export const dashboardMetrics: DashboardMetric[] = [
  {
    id: "documents",
    kind: "documents",
    label: "MEDICAL DOCUMENTS",
    value: "12",
    delta: "3 added this month",
  },
  {
    id: "events",
    kind: "events",
    label: "MEDICAL EVENTS",
    value: "27",
    delta: "Across 6 visits",
  },
  {
    id: "medications",
    kind: "medications",
    label: "ACTIVE MEDICATIONS",
    value: "5",
    delta: "2 started in June",
  },
  {
    id: "findings",
    kind: "findings",
    label: "AI FINDINGS",
    value: "3",
    delta: "1 needs prompt attention",
  },
  {
    id: "priority",
    kind: "priority",
    label: "HIGH PRIORITY",
    value: "1",
    delta: "Consultation recommended",
  },
];

/** Figma: 07 · Dashboard — panel · Recent activity (node 21:134). */
export const recentActivity: {
  id: string;
  tone: "risk" | "ok" | "warn";
  title: string;
  meta: string;
}[] = [
  {
    id: "activity-1",
    tone: "risk",
    title: "New high-risk finding raised",
    meta: "Allergy contradiction · 2 hours ago",
  },
  {
    id: "activity-2",
    tone: "ok",
    title: "Prescription_June.pdf processed",
    meta: "Extracted 3 medications · 2 hours ago",
  },
  {
    id: "activity-3",
    tone: "warn",
    title: "Haemoglobin trend updated",
    meta: "Third consecutive decline · 2 hours ago",
  },
  {
    id: "activity-4",
    tone: "ok",
    title: "Lab_Report_March.pdf processed",
    meta: "Extracted 8 results · 3 days ago",
  },
  {
    id: "activity-5",
    tone: "ok",
    title: "Doctor_Note_March.pdf processed",
    meta: "Allergy recorded · 3 days ago",
  },
];

/** Figma: 07 · Dashboard — panel · Haemoglobin trend (node 20:171). */
export const haemoglobinTrend = {
  title: "Haemoglobin trend",
  unit: "g/dL",
  referenceLow: 13,
  referenceHigh: 17,
  referenceLabel: "AI explanation · reference range 13.0 – 17.0 g/dL",
  explanation:
    "Haemoglobin has fallen at each of the last three tests and the June result is below the reference range. This is a downward trend rather than a one-off reading, and is worth raising with a healthcare professional.",
  points: [
    { date: "Jan 2026", value: 13.5, documentId: "doc-6" },
    { date: "Mar 2026", value: 12.1, documentId: "doc-3" },
    { date: "Jun 2026", value: 10.8, documentId: "doc-1" },
  ],
};
/** Figma: 05 · Upload & OCR Pipeline — file list (nodes 24:504 / 24:512 / 24:525). */
export const demoUploadItems: UploadItem[] = [
  {
    id: "upload-1",
    fileName: "Prescription_June.pdf",
    sizeLabel: "2.4 MB",
    progress: 100,
    status: "analyzing",
    message: "Text extracted with PyMuPDF · analysing",
  },
  {
    id: "upload-2",
    fileName: "Scanned_Prescription_Jan.jpg",
    sizeLabel: "1.1 MB",
    progress: 62,
    status: "extracting",
    message: "No selectable text found · running Tesseract OCR",
  },
  {
    id: "upload-3",
    fileName: "Xray_Report_2025.tiff",
    sizeLabel: "8.2 MB",
    progress: 0,
    status: "failed",
    message: "Unsupported file type — rejected at validation",
  },
];

/** Figma: PROCESSING PIPELINE row (node 24:536). */
export const uploadPipelineSteps: PipelineStep[] = [
  { id: "validate", title: "Validate", description: "File type and size checks", status: "done" },
  { id: "store", title: "Store", description: "Saved to your private storage", status: "done" },
  { id: "classify", title: "Classify", description: "Document type detected", status: "done" },
  { id: "extract", title: "Extract text", description: "PyMuPDF text layer", status: "active" },
  { id: "ocr", title: "OCR", description: "Tesseract for scanned pages", status: "active" },
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

/** Figma: 12 · Ask AI — thread (node 30:951). */
export const chatHistory: ChatMessage[] = [
  {
    id: "msg-1",
    role: "user",
    paragraphs: [
      "Was my new medication prescribed despite the allergy mentioned in my previous report?",
    ],
  },
  {
    id: "msg-2",
    role: "assistant",
    paragraphs: [
      "Yes — based on your records, there is a contradiction. Your March doctor’s note records a penicillin allergy and advises avoiding penicillin-class antibiotics. The prescription issued on 12 June includes amoxicillin, which is in that class. Nothing in your uploaded records shows the allergy being reassessed between those two visits.",
      "This is a potential contradiction between two documents, not a confirmed reaction. Please confirm with the prescribing doctor or a pharmacist before your next dose.",
    ],
    citations: [
      {
        documentId: "doc-2",
        documentTitle: "Doctor_Note_March.pdf",
        page: 1,
        quote: "Allergy: Penicillin — presenting as rash.",
      },
      {
        documentId: "doc-1",
        documentTitle: "Prescription_June.pdf",
        page: 1,
        quote: "Amoxicillin 500 mg — three times daily.",
      },
    ],
    confidence: 94,
    guidance: "Consider consulting a qualified healthcare professional",
  },
  {
    id: "msg-3",
    role: "user",
    paragraphs: ["How has my haemoglobin changed this year?"],
  },
  {
    id: "msg-4",
    role: "assistant",
    paragraphs: [
      "It has fallen at each of your three tests: 13.5 g/dL in January, 12.1 g/dL in March and 10.8 g/dL in June. The June result is below the reference range of 13.0 – 17.0 g/dL used by the reporting lab.",
      "That is a consistent downward direction across five months rather than a single unusual reading.",
    ],
    citations: [
      {
        documentId: "doc-6",
        documentTitle: "Blood_Report_January.pdf",
        page: 2,
        quote: "Haemoglobin 13.5 g/dL (13.0 – 17.0).",
      },
      {
        documentId: "doc-1",
        documentTitle: "Lab_Report_June.pdf",
        page: 1,
        quote: "Haemoglobin 10.8 g/dL — below reference range.",
      },
    ],
    confidence: 91,
    guidance: "Worth raising at your next appointment",
  },
];

/** Figma: 13 · Ask AI — No-Diagnosis Safety — thread (node 32:951). */
export const safetyChatHistory: ChatMessage[] = [
  {
    id: "safety-1",
    role: "user",
    paragraphs: ["What disease do I have?"],
  },
  {
    id: "safety-2",
    role: "assistant",
    paragraphs: [
      "Naming a disease is a clinical judgement that requires examination, history and testing — outside what this system does. What I can do is explain what is written in your records, show where each statement came from, and flag where two documents appear to disagree.",
    ],
    refusal: {
      overline: "NOT A DIAGNOSIS",
      headline: "I cannot provide a medical diagnosis.",
      suggestions: [
        "Which of my results are outside the reference range?",
        "What has changed in my medications since January?",
      ],
      footnote:
        "For an interpretation of what your records mean, please consult a qualified healthcare professional.",
    },
  },
  {
    id: "safety-3",
    role: "user",
    paragraphs: [
      "Fine — is my haemoglobin something I should be worried about?",
    ],
  },
  {
    id: "safety-4",
    role: "assistant",
    paragraphs: [
      "I can tell you what your records show, but not whether you should worry — that judgement belongs to a clinician who can see the full picture. Your haemoglobin measured 13.5, 12.1 and 10.8 g/dL in January, March and June. The June value sits below the reporting lab’s reference range of 13.0 – 17.0 g/dL, and the direction has been downward at every test.",
    ],
    citations: [
      {
        documentId: "doc-6",
        documentTitle: "Blood_Report_January.pdf",
        page: 2,
        quote: "Haemoglobin 13.5 g/dL (13.0 – 17.0).",
      },
      {
        documentId: "doc-1",
        documentTitle: "Lab_Report_June.pdf",
        page: 1,
        quote: "Haemoglobin 10.8 g/dL — below reference range.",
      },
    ],
    cta: {
      label: "Find a healthcare professional nearby",
      note: "Recommended because this finding is high risk",
    },
  },
];

/** Figma: 12 · panel · how it works (node 30:1032). */
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

/** Figma: 13 · panel · Enforced safety rules (node 32:1032). */
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
/** Figma: 14 · Provider Search Setup — panel · how search works (node 33:1207). */
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
  location: "Jaffna",
  geocodeNote:
    "Resolved via Nominatim to 9.6615 N, 80.0255 E. Your location is used for this search only and is not stored alongside your medical records.",
  availability: "evenings",
  radiusKm: 10,
  availabilityNote:
    "Availability is treated as a preference for ranking. MediGuardian never invents appointment times — only opening hours published in OpenStreetMap are shown, and providers without published hours are labelled “Not available”.",
  suitableProfessional: {
    title: "Prescribing Doctor / Pharmacist",
    rationale:
      "Allergy and medication findings route to the prescriber or a pharmacist. Heart-related findings would route to a cardiologist instead.",
  },
};

export const providerWhyCard = {
  title: "Why you are being recommended to consult a professional",
  body: "Finding: potential allergy contradiction — a penicillin-class antibiotic was prescribed on 12 June despite a penicillin allergy recorded on 12 March. Confidence 94%.",
  findingId: "allergy-contradiction",
};

/** Figma: 15 · Provider Results — panel · providers (node 35:1222). */
export const providers: Provider[] = [
  {
    id: "jaffna-teaching-hospital",
    name: "Jaffna Teaching Hospital",
    kind: "hospital",
    specialties: ["General medicine · on-site pharmacy"],
    address: "Hospital Road, Jaffna",
    distanceKm: 2.1,
    openingHours: "Open 24 hours",
    phone: "+94 21 222 3348",
    matchScore: 92,
    matchBreakdown: [56, 38, 21, 18],
    coordinates: { lat: 9.6698, lng: 80.0206 },
    mapPosition: { top: 42, left: 46 },
  },
  {
    id: "green-cross-pharmacy",
    name: "Green Cross Pharmacy",
    kind: "pharmacy",
    specialties: ["Dispensing pharmacist"],
    address: "Kasthuriyar Road, Jaffna",
    distanceKm: 1.4,
    openingHours: "Mon–Sat 08:00 – 21:00",
    phone: "+94 21 222 7014",
    matchScore: 88,
    matchBreakdown: [50, 42, 18, 12],
    coordinates: { lat: 9.6634, lng: 80.0136 },
    mapPosition: { top: 50, left: 28 },
  },
  {
    id: "nallur-medical-centre",
    name: "Nallur Medical Centre",
    kind: "clinic",
    specialties: ["General practice · evening clinic"],
    address: "Point Pedro Road, Nallur",
    distanceKm: 3.6,
    openingHours: "Mon–Fri 17:00 – 21:00",
    phone: "+94 21 221 7790",
    matchScore: 85,
    matchBreakdown: [48, 32, 21, 14],
    coordinates: { lat: 9.6749, lng: 80.0301 },
    mapPosition: { top: 63, left: 65 },
  },
  {
    id: "central-dispensary",
    name: "Central Dispensary",
    kind: "pharmacy",
    specialties: ["Dispensing pharmacist"],
    address: "Stanley Road, Jaffna",
    distanceKm: 4.7,
    matchScore: 71,
    matchBreakdown: [46, 26, 6, 8],
    coordinates: { lat: 9.6591, lng: 80.0089 },
    mapPosition: { top: 71, left: 17 },
  },
];

export const providerResultsNote =
  "Result 4 is ranked lower because OpenStreetMap has no phone number or opening hours for it. Missing fields are shown as “Not available” rather than filled in.";

export const providerRankingWeights =
  "Specialty 40% · Distance 30% · Data completeness 15% · Other verified details 15%";

/** Figma: 16 · No Providers Found (node 37:1200). */
export const providerEmptyState = {
  headline: "No suitable healthcare providers were found in this area.",
  body: "OpenStreetMap has no healthcare facilities matching “Prescribing Doctor / Pharmacist” within 10 km of Jaffna. Rather than showing unrelated or invented results, we are telling you plainly that the search came back empty.",
  searchLog: [
    {
      label: "Geocoding",
      value: "Nominatim resolved “Jaffna” to 9.6615 N, 80.0255 E",
    },
    {
      label: "Overpass query",
      value: "amenity=doctors | pharmacy | clinic | hospital, radius 10 000 m",
    },
    { label: "Elements returned", value: "0" },
    { label: "Response time", value: "1.9 s · HTTP 200" },
  ],
  reassurance:
    "An empty result is a real answer. MediGuardian will never fill this space with generated clinics, addresses or phone numbers.",
};

/** Figma: 17 · Provider Service Unavailable (node 37:1635). */
export const providerErrorState = {
  headline: "We couldn’t retrieve healthcare providers right now.",
  body: "The OpenStreetMap service did not respond. This is a problem on our side of the lookup, not with your records. Please try again in a few minutes.",
  technical: [
    { label: "Failed step", value: "Overpass API — healthcare facility query" },
    { label: "Error", value: "HTTP 504 · gateway timeout after 30 s" },
    { label: "Retries", value: "2 of 2 attempts exhausted" },
    {
      label: "Succeeded before this",
      value: "Specialty matching · Nominatim geocoding (9.6615 N, 80.0255 E)",
    },
  ],
  reassurance:
    "Your documents, timeline and findings are unaffected — only the external provider lookup failed. No cached or substitute providers are shown in place of live data.",
};
/** Figma: 18 · Profile & Security — panel · Security (node 38:1506). */
export const securityToggles = [
  {
    id: "two-factor",
    title: "Two-factor authentication",
    description:
      "A code is required from your authenticator app at every sign-in.",
    enabled: true,
  },
  {
    id: "finding-alerts",
    title: "Alert me when a new finding is detected",
    description:
      "Sent to your email address only — findings are never included in the message body.",
    enabled: true,
  },
  {
    id: "idle-signout",
    title: "Automatic sign-out after 30 minutes idle",
    description: "Recommended on shared or public devices.",
    enabled: true,
  },
];

export const securitySessions: SecuritySession[] = [
  {
    id: "session-1",
    device: "Chrome on Windows",
    location: "Colombo, Sri Lanka",
    lastActive: "active now",
    current: true,
  },
  {
    id: "session-2",
    device: "Safari on iPhone",
    location: "Jaffna, Sri Lanka",
    lastActive: "last active 2 days ago",
    current: false,
  },
];

/** Figma: 18 · panel · Your data (node 38:1549). */
export const dataSummary = [
  { value: "8", label: "DOCUMENTS" },
  { value: "27", label: "EVENTS" },
  { value: "11.4 MB", label: "STORED" },
];

export const dataActions = [
  {
    id: "export",
    title: "Export everything",
    description: "Structured JSON plus your original uploaded files.",
  },
  {
    id: "log",
    title: "Download processing log",
    description: "Every extraction, AI call and provider search on your account.",
  },
];

/** Figma: 18 · panel · isolation (node 38:1580). */
export const isolationNotes = [
  {
    title: "Row-level security",
    description:
      "Every table is filtered by your user ID in the database itself, not only in application code.",
  },
  {
    title: "Per-user storage paths",
    description:
      "Files are stored under a private prefix keyed to your account and are never publicly listable.",
  },
  {
    title: "Signed, expiring links",
    description:
      "Opening a document generates a URL valid for 60 seconds. The link cannot be reused or shared.",
  },
  {
    title: "Scoped retrieval",
    description:
      "Vector search filters by your user ID before similarity ranking, so another account’s text can never enter your answers.",
  },
];

export const deleteDataNote =
  "Deletion is immediate and permanent. Files are removed from storage, rows are removed from the database, and embeddings are removed from the vector index.";
