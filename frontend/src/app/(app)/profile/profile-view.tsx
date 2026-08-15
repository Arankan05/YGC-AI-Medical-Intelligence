"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import {
  Calendar,
  Download,
  Loader2,
  LogIn,
  Pill,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { Field, fieldInputClass } from "@/components/field";
import { Panel, PanelHeader } from "@/components/panel";
import { RiskBadge } from "@/components/risk-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { api, toErrorMessage } from "@/lib/api";
import {
  securityToggles,
} from "@/lib/data";
import type {
  AllergyRecord,
  LabResult,
  MedicalOverview,
  UserProfile,
} from "@/lib/types";

type DangerAction = "documents" | "account" | null;

export function ProfileView() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [overview, setOverview] = useState<MedicalOverview | null>(null);
  const [allergies, setAllergies] = useState<AllergyRecord[]>([]);
  const [labs, setLabs] = useState<LabResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    fullName: "",
    phone: "",
    language: "",
    dateOfBirth: "",
  });
  const [toggles, setToggles] = useState(() =>
    Object.fromEntries(securityToggles.map((item) => [item.id, item.enabled]))
  );
  const [danger, setDanger] = useState<DangerAction>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadData() {
      try {
        const [profData, overviewData, allergyData, labData] = await Promise.all([
          api().getProfile(),
          api().getOverview().catch(() => null),
          api().listAllergies().catch(() => []),
          api().listLabResults().catch(() => []),
        ]);

        if (active) {
          setProfile(profData);
          setOverview(overviewData);
          setAllergies(allergyData || []);
          setLabs(labData || []);
          setEditForm({
            fullName: profData.fullName,
            phone: profData.phone === "—" ? "" : profData.phone,
            language: profData.language,
            dateOfBirth: profData.dateOfBirth === "—" ? "" : profData.dateOfBirth,
          });
          setLoading(false);
        }
      } catch (caught) {
        if (active) {
          setError(toErrorMessage(caught));
          setLoading(false);
        }
      }
    }

    loadData();

    return () => {
      active = false;
    };
  }, []);

  async function runDangerAction() {
    if (!danger) return;
    try {
      if (danger === "account") {
        await api().deleteAccount();
        setStatus("Account deletion requested.");
      } else {
        const docs = await api().listDocuments();
        for (const doc of docs) {
          await api().deleteDocument(doc.id);
        }
        setStatus("All documents deleted successfully.");
      }
    } catch (caught) {
      setStatus(toErrorMessage(caught));
    } finally {
      setDanger(null);
    }
  }

  async function runDataAction(id: string) {
    try {
      if (id === "export") {
        const blob = await api().exportAccountData();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `mediguardian-export-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        setStatus("Account data exported.");
      } else {
        await api().listDocuments();
        setStatus("Audit logs fetched.");
      }
    } catch (caught) {
      setStatus(toErrorMessage(caught));
    }
  }

  async function handleSaveProfile(event: FormEvent) {
    event.preventDefault();
    if (!profile) return;
    try {
      const updated = await api().updateProfile({
        fullName: editForm.fullName,
        legalName: editForm.fullName,
        phone: editForm.phone,
        language: editForm.language,
        dateOfBirth: editForm.dateOfBirth,
      });
      setProfile(updated);
      setEditing(false);
      setStatus("Profile updated successfully.");
    } catch (caught) {
      setStatus(toErrorMessage(caught));
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[400px] w-full items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-neutral-500">
          <Loader2 className="size-6 animate-spin text-brand-600" />
          <p className="text-sm">Loading patient profile...</p>
        </div>
      </div>
    );
  }

  if (error && !profile) {
    const isSessionError =
      error.toLowerCase().includes("session") || error.toLowerCase().includes("sign in");
    return (
      <div className="flex min-h-[400px] w-full flex-col items-center justify-center gap-4 px-4">
        <div className="max-w-md rounded-xl border border-neutral-200 bg-neutral-0 p-6 text-center shadow-card">
          <h3 className="text-base font-semibold text-neutral-900">
            {isSessionError ? "Sign In Required" : "Failed to Load Profile"}
          </h3>
          <p className="mt-2 text-sm text-neutral-600">
            {isSessionError
              ? "You are not currently signed in. Please sign in to view your profile and manage your medical records."
              : error}
          </p>
          <div className="mt-5 flex justify-center gap-3">
            {isSessionError ? (
              <Button render={<Link href="/sign-in" />} className="gap-2">
                <LogIn className="size-4" />
                Sign in to your account
              </Button>
            ) : (
              <Button
                onClick={() => {
                  setLoading(true);
                  setError(null);
                  api()
                    .getProfile()
                    .then((d) => {
                      setProfile(d);
                      setLoading(false);
                    })
                    .catch((e) => {
                      setError(toErrorMessage(e));
                      setLoading(false);
                    });
                }}
              >
                Retry
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (!profile) return null;

  const accountFields = [
    { label: "LEGAL FULL NAME", value: profile.legalName || profile.fullName || "—" },
    { label: "EMAIL ADDRESS", value: profile.email || "—" },
    { label: "PHONE NUMBER", value: profile.phone || "—" },
  ];
  const identityFields = [
    { label: "DATE OF BIRTH", value: profile.dateOfBirth || "—" },
    { label: "PATIENT ID", value: profile.id || "—" },
    { label: "PREFERRED LANGUAGE", value: profile.language || "English" },
  ];

  const totalDocs = overview?.totalDocuments ?? 0;
  const totalMeds = overview?.totalMedications ?? 0;
  const totalFindings = overview?.totalFindings ?? 0;
  const totalEvents = overview?.totalEvents ?? 0;
  const totalLabs = overview?.totalLabResults ?? labs.length;
  const totalAllergies = overview?.totalAllergies ?? allergies.length;

  const activeMeds = overview?.activeMedications ?? [];
  const priorityFindings = overview?.priorityFindings ?? [];
  const recentEvents = overview?.recentEvents ?? [];

  return (
    <div className="flex min-h-full w-full flex-col gap-5 px-4 py-[22px] md:px-[26px]">
      {/* Top Patient Hero & Information */}
      <Panel>
        <PanelHeader title="Patient Profile & Demographics" className="py-3" />
        <div className="flex flex-col gap-4 px-[18px] pt-[15px] pb-4">
          <div className="flex w-full flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-brand-700 text-lg font-semibold text-neutral-0 shadow-sm">
                {profile.initials}
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="text-xl font-bold tracking-tight text-neutral-900">
                  {profile.fullName}
                </span>
                <span className="text-[13px] text-neutral-500">
                  {profile.accountType} · Patient Record since {profile.memberSince}
                </span>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="px-4 py-2"
              onClick={() => setEditing(true)}
            >
              Edit Profile Info
            </Button>
          </div>

          <dl className="grid grid-cols-1 gap-4 border-t border-neutral-100 pt-4 sm:grid-cols-2 lg:grid-cols-3">
            {accountFields.map((field) => (
              <div key={field.label} className="flex flex-col gap-0.5">
                <dt className="type-overline text-neutral-500">{field.label}</dt>
                <dd className="text-sm font-medium text-neutral-800">{field.value}</dd>
              </div>
            ))}
            {identityFields.map((field) => (
              <div key={field.label} className="flex flex-col gap-0.5">
                <dt className="type-overline text-neutral-500">{field.label}</dt>
                <dd className="text-sm font-medium text-neutral-800">{field.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Panel>

      {/* AI Clinical Summary Banner */}
      {overview?.latestSummary && (
        <div className="flex w-full flex-col gap-2.5 rounded-xl border border-brand-200 bg-brand-50/70 p-4 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4 text-brand-700" />
              <h3 className="text-sm font-semibold text-brand-900">
                AI Executive Medical Summary
              </h3>
            </div>
            {overview.confidenceScore !== undefined && (
              <span className="rounded-full bg-brand-100 px-2.5 py-0.5 text-xs font-semibold text-brand-800">
                Confidence:{" "}
                {Math.round(
                  overview.confidenceScore <= 1
                    ? overview.confidenceScore * 100
                    : overview.confidenceScore
                )}
                %
              </span>
            )}
          </div>
          <p className="text-[13px] leading-[21px] text-neutral-800">
            {overview.latestSummary}
          </p>
          <p className="text-[11px] text-neutral-500 italic">
            AI-extracted clinical summary · Always verify medical information with a qualified healthcare professional.
          </p>
        </div>
      )}

      {/* Record Statistics Grid */}
      <div>
        <h3 className="type-overline mb-2 text-neutral-500">
          HEALTH RECORD STATISTICS
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Link
            href="/documents"
            className="flex flex-col gap-1 rounded-xl border border-neutral-200 bg-neutral-0 p-3.5 shadow-card transition-colors hover:border-brand-300"
          >
            <span className="type-overline text-neutral-500">DOCUMENTS</span>
            <span className="text-2xl font-bold text-neutral-900">{totalDocs}</span>
            <span className="text-xs text-brand-700">View all →</span>
          </Link>
          <Link
            href="/medications"
            className="flex flex-col gap-1 rounded-xl border border-neutral-200 bg-neutral-0 p-3.5 shadow-card transition-colors hover:border-brand-300"
          >
            <span className="type-overline text-neutral-500">MEDICATIONS</span>
            <span className="text-2xl font-bold text-neutral-900">{totalMeds}</span>
            <span className="text-xs text-brand-700">View active →</span>
          </Link>
          <Link
            href="/findings"
            className="flex flex-col gap-1 rounded-xl border border-neutral-200 bg-neutral-0 p-3.5 shadow-card transition-colors hover:border-brand-300"
          >
            <span className="type-overline text-neutral-500">FINDINGS</span>
            <span className="text-2xl font-bold text-neutral-900">{totalFindings}</span>
            <span className="text-xs text-brand-700">View alerts →</span>
          </Link>
          <Link
            href="/timeline"
            className="flex flex-col gap-1 rounded-xl border border-neutral-200 bg-neutral-0 p-3.5 shadow-card transition-colors hover:border-brand-300"
          >
            <span className="type-overline text-neutral-500">EVENTS</span>
            <span className="text-2xl font-bold text-neutral-900">{totalEvents}</span>
            <span className="text-xs text-brand-700">Timeline →</span>
          </Link>
          <Link
            href="/lab-results"
            className="flex flex-col gap-1 rounded-xl border border-neutral-200 bg-neutral-0 p-3.5 shadow-card transition-colors hover:border-brand-300"
          >
            <span className="type-overline text-neutral-500">LAB RESULTS</span>
            <span className="text-2xl font-bold text-neutral-900">{totalLabs}</span>
            <span className="text-xs text-brand-700">Biomarkers →</span>
          </Link>
          <Link
            href="/allergies"
            className="flex flex-col gap-1 rounded-xl border border-neutral-200 bg-neutral-0 p-3.5 shadow-card transition-colors hover:border-brand-300"
          >
            <span className="type-overline text-neutral-500">ALLERGIES</span>
            <span className="text-2xl font-bold text-neutral-900">{totalAllergies}</span>
            <span className="text-xs text-brand-700">Allergen log →</span>
          </Link>
        </div>
      </div>

      {/* Main 2-Column Clinical Overview */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Left Column: Medications & Allergies */}
        <div className="flex flex-col gap-5">
          {/* Current Medications Panel */}
          <Panel>
            <PanelHeader
              title="Current Medications"
              actions={
                <Link
                  href="/medications"
                  className="text-xs font-semibold text-brand-700 hover:underline"
                >
                  Manage ({activeMeds.length})
                </Link>
              }
            />
            <div className="flex flex-col divide-y divide-neutral-100 p-4">
              {activeMeds.map((med) => (
                <div key={med.id} className="flex items-start justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                  <div className="flex items-start gap-2.5">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded bg-brand-50 text-brand-700">
                      <Pill className="size-3.5" />
                    </span>
                    <div className="flex flex-col">
                      <span className="text-[13px] font-semibold text-neutral-900">{med.name}</span>
                      <span className="text-xs text-neutral-500">
                        {med.dosage} · {med.frequency}
                        {med.instructions && ` · ${med.instructions}`}
                      </span>
                    </div>
                  </div>
                  <span className="type-overline rounded-full bg-status-ok-bg px-2 py-0.5 text-status-ok">
                    ACTIVE
                  </span>
                </div>
              ))}
              {activeMeds.length === 0 && (
                <p className="py-4 text-center text-xs text-neutral-500">
                  No active medication records. Prescriptions will appear here upon document extraction.
                </p>
              )}
            </div>
          </Panel>

          {/* Known Allergies Panel */}
          <Panel>
            <PanelHeader
              title="Known Drug Allergies"
              actions={
                <Link
                  href="/allergies"
                  className="text-xs font-semibold text-brand-700 hover:underline"
                >
                  View All ({allergies.length})
                </Link>
              }
            />
            <div className="flex flex-col divide-y divide-neutral-100 p-4">
              {allergies.map((al) => (
                <div key={al.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                  <div className="flex items-center gap-2.5">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded bg-risk-high-bg text-risk-high">
                      <ShieldAlert className="size-3.5" />
                    </span>
                    <div className="flex flex-col">
                      <span className="text-[13px] font-semibold text-neutral-900">{al.medicationName}</span>
                      <span className="text-xs text-neutral-500">{al.reaction || "Reported reaction"}</span>
                    </div>
                  </div>
                  <span className="type-overline rounded-full bg-risk-high-bg px-2 py-0.5 text-risk-high">
                    {al.severity || "Moderate"}
                  </span>
                </div>
              ))}
              {allergies.length === 0 && (
                <p className="py-4 text-center text-xs text-neutral-500">
                  No drug allergies recorded for this patient.
                </p>
              )}
            </div>
          </Panel>
        </div>

        {/* Right Column: Priority Findings & Recent Events */}
        <div className="flex flex-col gap-5">
          {/* Priority AI Findings Panel */}
          <Panel>
            <PanelHeader
              title="Priority AI Findings & Contradictions"
              actions={
                <Link
                  href="/findings"
                  className="text-xs font-semibold text-brand-700 hover:underline"
                >
                  All findings ({priorityFindings.length})
                </Link>
              }
            />
            <div className="flex flex-col divide-y divide-neutral-100 p-4">
              {priorityFindings.map((finding) => (
                <div key={finding.id} className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <RiskBadge risk={finding.risk} />
                      <span className="text-[13px] font-semibold text-neutral-900">{finding.title}</span>
                    </div>
                    <span className="text-xs text-neutral-500">{finding.detectedOn}</span>
                  </div>
                  <p className="text-xs leading-5 text-neutral-600">{finding.summary}</p>
                </div>
              ))}
              {priorityFindings.length === 0 && (
                <p className="py-4 text-center text-xs text-neutral-500">
                  No priority clinical contradictions flagged.
                </p>
              )}
            </div>
          </Panel>

          {/* Recent Medical Events Panel */}
          <Panel>
            <PanelHeader
              title="Recent Medical Events"
              actions={
                <Link
                  href="/timeline"
                  className="text-xs font-semibold text-brand-700 hover:underline"
                >
                  Full Timeline ({recentEvents.length})
                </Link>
              }
            />
            <div className="flex flex-col divide-y divide-neutral-100 p-4">
              {recentEvents.map((ev) => (
                <div key={ev.id} className="flex items-start justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                  <div className="flex items-start gap-2.5">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded bg-neutral-100 text-neutral-700">
                      <Calendar className="size-3.5" />
                    </span>
                    <div className="flex flex-col">
                      <span className="text-[13px] font-semibold text-neutral-900">{ev.title}</span>
                      <span className="text-xs text-neutral-600">{ev.summary}</span>
                    </div>
                  </div>
                  <span className="text-xs text-neutral-500 shrink-0">{ev.date}</span>
                </div>
              ))}
              {recentEvents.length === 0 && (
                <p className="py-4 text-center text-xs text-neutral-500">
                  No medical timeline events recorded yet.
                </p>
              )}
            </div>
          </Panel>
        </div>
      </div>

      {/* Account Security & Data Management */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {/* Security & Sessions */}
        <Panel>
          <PanelHeader title="Security & Authentication" />
          <div className="flex flex-col gap-3.5 p-4">
            {securityToggles.map((item) => (
              <div key={item.id} className="flex w-full items-center justify-between gap-3.5">
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-sm font-medium text-neutral-800">{item.title}</span>
                  <span className="text-xs text-neutral-500">{item.description}</span>
                </span>
                <Switch
                  checked={toggles[item.id]}
                  onCheckedChange={(checked) =>
                    setToggles((current) => ({ ...current, [item.id]: checked }))
                  }
                  aria-label={item.title}
                />
              </div>
            ))}
          </div>
        </Panel>

        {/* Data Ownership & Export */}
        <Panel>
          <PanelHeader title="Patient Data Governance" />
          <div className="flex flex-col gap-3.5 p-4">
            <p className="text-xs leading-5 text-neutral-600">
              MediGuardian AI enforces strict row-level isolation. You own your clinical data and can export it or purge it at any time.
            </p>
            <div className="flex flex-wrap gap-2.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => runDataAction("export")}
                className="gap-1.5 text-xs"
              >
                <Download className="size-3.5" />
                Export Full Health Data (JSON)
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDanger("documents")}
                className="border-risk-high-border text-risk-high hover:bg-risk-high-bg text-xs"
              >
                Purge Uploaded Documents
              </Button>
            </div>
            {status && (
              <p className="rounded-md bg-neutral-50 px-3 py-2 text-xs text-neutral-700">
                {status}
              </p>
            )}
          </div>
        </Panel>
      </div>

      {/* Edit Profile Modal Dialog */}
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="max-w-md">
          <DialogTitle>Edit Patient Profile</DialogTitle>
          <DialogDescription>
            Update your demographic and patient contact details.
          </DialogDescription>
          <form onSubmit={handleSaveProfile} className="mt-4 flex flex-col gap-3.5">
            <Field label="Legal Full Name">
              <input
                type="text"
                value={editForm.fullName}
                onChange={(e) =>
                  setEditForm({ ...editForm, fullName: e.target.value })
                }
                className={fieldInputClass}
                required
              />
            </Field>
            <Field label="Phone Number">
              <input
                type="tel"
                value={editForm.phone}
                onChange={(e) =>
                  setEditForm({ ...editForm, phone: e.target.value })
                }
                className={fieldInputClass}
                placeholder="+1 (555) 000-0000"
              />
            </Field>
            <Field label="Date of Birth">
              <input
                type="date"
                value={editForm.dateOfBirth}
                onChange={(e) =>
                  setEditForm({ ...editForm, dateOfBirth: e.target.value })
                }
                className={fieldInputClass}
              />
            </Field>
            <Field label="Preferred Language">
              <input
                type="text"
                value={editForm.language}
                onChange={(e) =>
                  setEditForm({ ...editForm, language: e.target.value })
                }
                className={fieldInputClass}
              />
            </Field>
            <div className="mt-2 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditing(false)}
              >
                Cancel
              </Button>
              <Button type="submit">Save Changes</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Danger Action Confirmation Dialog */}
      <Dialog open={Boolean(danger)} onOpenChange={(open) => !open && setDanger(null)}>
        <DialogContent className="max-w-md">
          <DialogTitle className="text-risk-high">
            {danger === "account" ? "Delete Patient Account?" : "Purge Medical Documents?"}
          </DialogTitle>
          <DialogDescription>
            {danger === "account"
              ? "This will permanently delete your patient profile, documents, and all extracted intelligence. This action cannot be undone."
              : "This will delete all uploaded medical files and associated extracted records from your account."}
          </DialogDescription>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDanger(null)}>
              Cancel
            </Button>
            <Button
              onClick={runDangerAction}
              className="bg-risk-high text-neutral-0 hover:bg-risk-high/90"
            >
              Confirm Deletion
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
