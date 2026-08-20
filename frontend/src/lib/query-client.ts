import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";

/**
 * Global QueryClient instance configured for MediGuardian AI.
 * 
 * - Default staleTime of 5 minutes avoids redundant re-fetching when navigating pages.
 * - refetchOnWindowFocus is disabled to prevent unexpected network churn during clinical workflows.
 * - Failed queries retry at most once, and authentication/authorization errors (401/403) are never retried.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          return false;
        }
        if (error instanceof Error) {
          const msg = error.message.toLowerCase();
          if (
            msg.includes("401") ||
            msg.includes("403") ||
            msg.includes("unauthorized") ||
            msg.includes("forbidden") ||
            msg.includes("no active session")
          ) {
            return false;
          }
        }
        return failureCount < 1;
      },
    },
  },
});

/**
 * Purges all cached medical data from memory.
 * Must be called during sign-out or session revocation to enforce tenant data isolation.
 */
export function clearMedicalCache(): void {
  queryClient.clear();
}
