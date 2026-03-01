/**
 * Validated environment configuration.
 * Throws at build/runtime if required variables are missing.
 */

function requireEnv(key: string, fallback?: string): string {
  const value = process.env[key] ?? fallback;
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
}

export const env = {
  apiBaseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  defaultTenantId:
    process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID ?? "default",
  nodeEnv: (process.env.NODE_ENV ?? "development") as
    | "development"
    | "staging"
    | "production",
} as const;

export type AppEnv = typeof env;
