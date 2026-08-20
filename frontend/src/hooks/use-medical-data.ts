"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AllergyRecord,
  Finding,
  LabResult,
  MedicalDocument,
  MedicalOverview,
  Medication,
  TimelineEvent,
  UserProfile,
} from "@/lib/types";

/**
 * Fetches the authenticated user profile.
 * Cached for 5 minutes by default.
 */
export function useProfileQuery(enabled = true) {
  return useQuery<UserProfile>({
    queryKey: ["user", "profile"],
    queryFn: () => api().getProfile(),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Fetches medical overview aggregate counts and summaries.
 * Query key is strictly scoped by user ID to enforce tenant data isolation.
 */
export function useOverviewQuery(userId?: string, enabled = true) {
  return useQuery<MedicalOverview>({
    queryKey: ["user", userId || "anonymous", "overview"],
    queryFn: () => api().getOverview(),
    enabled: Boolean(enabled && userId),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Shared query for clinical findings.
 * Reused between AppShell (for notification badges) and DashboardPage / Findings pages.
 * Prevents duplicate HTTP requests for the same user.
 */
export function useFindingsQuery(userId?: string, enabled = true) {
  return useQuery<Finding[]>({
    queryKey: ["user", userId || "anonymous", "findings"],
    queryFn: () => api().listFindings(),
    enabled: Boolean(enabled && userId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useDocumentsQuery(userId?: string, enabled = true) {
  return useQuery<MedicalDocument[]>({
    queryKey: ["user", userId || "anonymous", "documents"],
    queryFn: () => api().listDocuments(),
    enabled: Boolean(enabled && userId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMedicationsQuery(userId?: string, enabled = true) {
  return useQuery<Medication[]>({
    queryKey: ["user", userId || "anonymous", "medications"],
    queryFn: () => api().listMedications(),
    enabled: Boolean(enabled && userId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTimelineQuery(userId?: string, enabled = true) {
  return useQuery<TimelineEvent[]>({
    queryKey: ["user", userId || "anonymous", "timeline"],
    queryFn: () => api().listTimeline(),
    enabled: Boolean(enabled && userId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAllergiesQuery(userId?: string, enabled = true) {
  return useQuery<AllergyRecord[]>({
    queryKey: ["user", userId || "anonymous", "allergies"],
    queryFn: () => api().listAllergies(),
    enabled: Boolean(enabled && userId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useLabIntelligenceQuery(userId?: string, enabled = true) {
  return useQuery<LabResult[]>({
    queryKey: ["user", userId || "anonymous", "lab-intelligence"],
    queryFn: () => api().listLabIntelligence(),
    enabled: Boolean(enabled && userId),
    staleTime: 5 * 60 * 1000,
  });
}
