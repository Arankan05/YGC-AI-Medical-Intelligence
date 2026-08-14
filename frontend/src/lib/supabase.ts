import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

/**
 * Singleton Supabase client instance initialized with public configuration.
 * Only NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are used.
 */
let supabaseClientInstance: SupabaseClient | null = null;

if (supabaseUrl && supabaseAnonKey) {
  supabaseClientInstance = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });
}

export const supabase = supabaseClientInstance;

/**
 * Returns the active Supabase client instance or throws a helpful configuration error.
 */
export function getSupabase(): SupabaseClient {
  if (!supabaseClientInstance) {
    throw new Error(
      "Supabase client is not configured. Please ensure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are set in .env.local."
    );
  }
  return supabaseClientInstance;
}

/**
 * Retrieves the current Supabase JWT access token for authenticating API calls.
 * Automatically refreshes the session if expiring soon.
 * Returns null if the user is not authenticated or Supabase is not configured.
 */
export async function getAccessToken(): Promise<string | null> {
  if (!supabaseClientInstance) {
    return null;
  }
  try {
    const {
      data: { session },
      error,
    } = await supabaseClientInstance.auth.getSession();

    if (error || !session) {
      return null;
    }

    // Check if token expires within 30 seconds and refresh if needed
    const expiresAt = session.expires_at;
    const now = Math.floor(Date.now() / 1000);
    if (expiresAt && expiresAt - now < 30) {
      const {
        data: { session: refreshedSession },
        error: refreshError,
      } = await supabaseClientInstance.auth.refreshSession();
      if (!refreshError && refreshedSession) {
        return refreshedSession.access_token;
      }
    }

    return session.access_token;
  } catch (err) {
    console.error("Error retrieving Supabase access token:", err);
    return null;
  }
}
