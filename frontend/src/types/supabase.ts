/**
 * Supabase type definitions for ChessIQ.
 *
 * The Database generic type will be replaced by the generated output of
 * `supabase gen types typescript` once the schema is finalised. Until then
 * we use a permissive placeholder so the clients compile without errors.
 *
 * To regenerate:
 *   npx supabase gen types typescript --project-id zfcidmlsstfgykpnnyjp > src/types/supabase.ts
 *
 * After regeneration, keep only the Database export below and remove this
 * placeholder block.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Database = Record<string, any>

/**
 * Convenience re-exports so the rest of the codebase can import auth types
 * from a single location instead of reaching into supabase-js directly.
 *
 * Future premium subscription tiers and user roles will extend SupabaseUser
 * via app_metadata (never user_metadata, which is user-editable).
 */
export type { User as SupabaseUser, Session as SupabaseSession } from '@supabase/supabase-js'
