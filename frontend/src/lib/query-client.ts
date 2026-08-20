import { QueryClient } from "@tanstack/react-query";

/**
 * Global QueryClient instance configured for MediGuardian AI.
 * 
 * - Default staleTime of 5 minutes avoids redundant re-fetching when navigating pages.
 * - refetchOnWindowFocus is disabled to prevent unexpected network churn during clinical workflows.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
      retry: 1,
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
