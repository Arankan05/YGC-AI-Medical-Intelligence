"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Download, FileClock, Loader2, Lock, Monitor, Smartphone } from "lucide-react";

import { Field, fieldInputClass } from "@/components/field";
import { Panel, PanelHeader } from "@/components/panel";
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
  dataActions,
  deleteDataNote,
  isolationNotes,
  securitySessions,
  securityToggles,
} from "@/lib/data";
import type { UserProfile } from "@/lib/types";

type DangerAction = "documents" | "account" | null;

export function ProfileView() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    fullName: "",
    phone: "",
    language: "",
    dateOfBirth: "",
  });
  const [docCount, setDocCount] = useState<number | null>(null);
  const [toggles, setToggles] = useState(() =>
    Object.fromEntries(securityToggles.map((item) => [item.id, item.enabled]))
  );
  const [sessions, setSessions] = useState(securitySessions);
  const [danger, setDanger] = useState<DangerAction>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api()
      .getProfile()
      .then((data) => {
        if (active) {
          setProfile(data);
          setEditForm({
            fullName: data.fullName,
            phone: data.phone === "—" ? "" : data.phone,
            language: data.language,
            dateOfBirth: data.dateOfBirth === "—" ? "" : data.dateOfBirth,
          });
          setLoading(false);
        }
      })
      .catch((caught) => {
        if (active) {
          setError(toErrorMessage(caught));
          setLoading(false);
        }
      });

    api()
      .listDocuments()
      .then((docs) => {
        if (active) setDocCount(docs.length);
      })
      .catch(() => {
        if (active) setDocCount(0);
      });

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
        setDocCount(0);
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
          <p className="text-sm">Loading user profile...</p>
        </div>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="flex min-h-[400px] w-full flex-col items-center justify-center gap-4 px-4">
        <div className="max-w-md rounded-xl border border-risk-high-border bg-risk-high-bg p-6 text-center">
          <h3 className="text-base font-semibold text-risk-high">
            Failed to Load Profile
          </h3>
          <p className="mt-2 text-sm text-neutral-700">{error}</p>
          <Button
            className="mt-4"
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
        </div>
      </div>
    );
  }

  if (!profile) return null;

  const accountFields = [
    { label: "FULL NAME", value: profile.legalName || profile.fullName || "—" },
    { label: "EMAIL", value: profile.email || "—" },
    { label: "PHONE", value: profile.phone || "—" },
  ];
  const identityFields = [
    { label: "DATE OF BIRTH", value: profile.dateOfBirth || "—" },
    { label: "PATIENT ID", value: profile.id || "—" },
    { label: "PREFERRED LANGUAGE", value: profile.language || "English" },
  ];

  return (
    <div className="flex min-h-full w-full flex-col gap-3.5 px-4 py-[22px] md:px-[26px] xl:flex-row xl:items-stretch">
      <div className="flex w-full min-w-0 flex-1 flex-col gap-3.5">
        {/* panel · Account (38:1472) */}
        <Panel>
          <PanelHeader title="Account" className="py-3" />
          <div className="flex flex-col gap-3.5 px-[18px] pt-[15px] pb-4">
            <div className="flex w-full flex-wrap items-center gap-3.5">
              <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-brand-700 text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-0">
                {profile.initials}
              </span>
              <span className="flex min-w-[200px] flex-1 flex-col gap-[3px]">
                <span className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
                  {profile.fullName}
                </span>
                <span className="text-[13px] leading-[19px] text-neutral-500">
                  {profile.accountType} · member since {profile.memberSince}
                </span>
              </span>
              <Button
                variant="outline"
                size="sm"
                className="px-[15px] py-[9px]"
                onClick={() => setEditing(true)}
              >
                Edit profile
              </Button>
            </div>

            <dl className="flex w-full flex-wrap gap-x-6 gap-y-[13px]">
              <div className="flex min-w-[220px] flex-1 flex-col gap-[13px]">
                {accountFields.map((field) => (
                  <div key={field.label} className="flex flex-col gap-[3px]">
                    <dt className="type-overline text-neutral-500">
                      {field.label}
                    </dt>
                    <dd className="text-sm leading-[21px] text-neutral-800">
                      {field.value}
                    </dd>
                  </div>
                ))}
              </div>
              <div className="flex min-w-[220px] flex-1 flex-col gap-[13px]">
                {identityFields.map((field) => (
                  <div key={field.label} className="flex flex-col gap-[3px]">
                    <dt className="type-overline text-neutral-500">
                      {field.label}
                    </dt>
                    <dd className="text-sm leading-[21px] text-neutral-800">
                      {field.value}
                    </dd>
                  </div>
                ))}
              </div>
            </dl>
          </div>
        </Panel>

        {/* panel · Security (38:1506) */}
        <Panel>
          <PanelHeader title="Security" className="py-3" />
          <div className="flex flex-col gap-3.5 px-[18px] pt-[15px] pb-4">
            {securityToggles.map((item) => (
              <div key={item.id} className="flex w-full items-center gap-3.5">
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-sm leading-5 font-medium text-neutral-800">
                    {item.title}
                  </span>
                  <span className="text-xs leading-4 font-medium text-neutral-500">
                    {item.description}
                  </span>
                </span>
                <Switch
                  checked={toggles[item.id]}
                  onCheckedChange={(checked) =>
                    setToggles((current) => ({ ...current, [item.id]: checked }))
                  }
                  aria-label={item.title}
                  className="data-[checked]:bg-brand-600"
                />
              </div>
            ))}

            <div className="h-px w-full bg-neutral-200" />
            <p className="type-overline text-neutral-500">ACTIVE SESSIONS</p>

            {sessions.map((session) => {
              const Icon = session.current ? Monitor : Smartphone;
              return (
                <div
                  key={session.id}
                  className="flex w-full items-center gap-3 rounded-[9px] bg-neutral-50 px-3.5 py-[11px]"
                >
                  <Icon
                    className="size-4 shrink-0 text-neutral-600"
                    strokeWidth={1.8}
                  />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="text-[13px] leading-[18px] font-medium text-neutral-800">
                      {session.device}
                    </span>
                    <span className="text-xs leading-4 font-medium text-neutral-500">
                      {session.location} · {session.lastActive}
                    </span>
                  </span>
                  {session.current ? (
                    <span className="type-overline shrink-0 rounded-full bg-status-ok-bg px-2.5 py-[3px] text-status-ok">
                      THIS DEVICE
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        setSessions((current) =>
                          current.filter((item) => item.id !== session.id)
                        )
                      }
                      className="shrink-0 cursor-pointer text-[13px] leading-[18px] font-medium text-risk-high hover:underline"
                    >
                      Sign out
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </Panel>
      </div>

      <div className="flex w-full flex-col gap-3.5 xl:w-[380px] xl:shrink-0">
        {/* panel · Your data (38:1549) */}
        <Panel>
          <PanelHeader title="Your data" className="py-3" />
          <div className="flex flex-col gap-3.5 px-[18px] pt-[15px] pb-4">
            <div className="flex w-full gap-3">
              <div className="flex flex-1 flex-col gap-0.5">
                <span className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
                  {docCount !== null ? docCount : "—"}
                </span>
                <span className="type-overline text-neutral-500">
                  DOCUMENTS
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-0.5">
                <span className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
                  {docCount !== null && docCount > 0 ? "—" : "0"}
                </span>
                <span className="type-overline text-neutral-500">
                  EXTRACTED EVENTS
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-0.5">
                <span className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
                  {docCount !== null && docCount > 0 ? "—" : "0"}
                </span>
                <span className="type-overline text-neutral-500">
                  ACTIVE MEDICATIONS
                </span>
              </div>
            </div>

            {dataActions.map((action) => {
              const Icon = action.id === "export" ? Download : FileClock;
              return (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => runDataAction(action.id)}
                  className="flex w-full cursor-pointer items-center gap-3 rounded-[9px] border border-neutral-200 bg-neutral-0 px-[13px] py-[11px] text-left transition-colors hover:bg-neutral-50"
                >
                  <Icon
                    className="size-4 shrink-0 text-brand-700"
                    strokeWidth={1.8}
                  />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="text-[13px] leading-[18px] font-medium text-neutral-800">
                      {action.title}
                    </span>
                    <span className="text-xs leading-4 font-medium text-neutral-500">
                      {action.description}
                    </span>
                  </span>
                </button>
              );
            })}

            {status && (
              <p
                role="status"
                className="rounded-md bg-neutral-50 px-3 py-2 text-xs leading-4 text-neutral-600"
              >
                {status}
              </p>
            )}
          </div>
        </Panel>

        {/* panel · isolation (38:1580) */}
        <div className="flex w-full flex-1 flex-col gap-[11px] rounded-xl border border-brand-200 bg-sidebar-bg px-4 py-[15px]">
          <div className="flex items-center gap-[9px]">
            <Lock className="size-4 shrink-0 text-brand-700" strokeWidth={1.8} />
            <p className="type-overline text-brand-700">
              HOW YOUR RECORDS ARE ISOLATED
            </p>
          </div>
          {isolationNotes.map((note) => (
            <div key={note.title} className="flex w-full flex-col gap-[3px]">
              <p className="text-[13px] leading-[18px] font-medium text-sidebar-ink">
                {note.title}
              </p>
              <p className="text-xs leading-4 font-medium text-sidebar-ink-muted">
                {note.description}
              </p>
            </div>
          ))}
        </div>

        {/* panel · danger (38:1598) */}
        <div className="flex w-full flex-col gap-[11px] rounded-xl border border-risk-high-border bg-risk-high-bg px-4 pt-3.5 pb-[15px]">
          <p className="type-overline text-risk-high">DELETE YOUR DATA</p>
          <p className="text-xs leading-4 font-medium text-neutral-700">
            {deleteDataNote}
          </p>
          <div className="flex flex-wrap gap-[9px]">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDanger("documents")}
              className="border-risk-high-border bg-neutral-0 px-3.5 py-[9px] text-risk-high hover:bg-risk-high-bg"
            >
              Delete all documents
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setDanger("account")}
              className="px-3.5 py-[9px]"
            >
              Delete account
            </Button>
          </div>
        </div>
      </div>

      {/* Edit profile */}
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="max-w-[420px] gap-4 p-6">
          <div className="flex flex-col gap-1">
            <DialogTitle className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
              Edit profile
            </DialogTitle>
            <DialogDescription className="text-[13px] leading-[19px] text-neutral-500">
              Changes are saved to your account only.
            </DialogDescription>
          </div>
          <form className="flex flex-col gap-4" onSubmit={handleSaveProfile}>
            <Field label="FULL NAME" htmlFor="fullName">
              <input
                id="fullName"
                value={editForm.fullName}
                onChange={(event) =>
                  setEditForm({ ...editForm, fullName: event.target.value })
                }
                className={fieldInputClass}
                placeholder="Enter full name"
              />
            </Field>
            <Field label="EMAIL" htmlFor="profileEmail">
              <input
                id="profileEmail"
                type="email"
                disabled
                value={profile.email}
                className={`${fieldInputClass} opacity-70 cursor-not-allowed`}
              />
            </Field>
            <Field label="PHONE" htmlFor="profilePhone">
              <input
                id="profilePhone"
                value={editForm.phone}
                onChange={(event) =>
                  setEditForm({ ...editForm, phone: event.target.value })
                }
                className={fieldInputClass}
                placeholder="Enter phone number"
              />
            </Field>
            <div className="flex justify-end gap-2.5">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setEditing(false);
                }}
              >
                Cancel
              </Button>
              <Button type="submit">Save changes</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Destructive confirmation */}
      <Dialog open={danger !== null} onOpenChange={(open) => !open && setDanger(null)}>
        <DialogContent className="max-w-[420px] gap-4 p-6">
          <div className="flex flex-col gap-1">
            <DialogTitle className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
              {danger === "account" ? "Delete account" : "Delete all documents"}
            </DialogTitle>
            <DialogDescription className="text-[13px] leading-[19px] text-neutral-600">
              {deleteDataNote}
            </DialogDescription>
          </div>
          <div className="flex justify-end gap-2.5">
            <Button
              type="button"
              variant="outline"
              onClick={() => setDanger(null)}
            >
              Cancel
            </Button>
            <Button type="button" variant="destructive" onClick={runDangerAction}>
              {danger === "account" ? "Delete account" : "Delete documents"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
