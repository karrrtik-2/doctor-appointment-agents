/**
 * Type-safe HTTP client for the Doctor Appointment Platform API.
 *
 * All calls are routed through Next.js rewrites at /api/backend/* so the
 * real backend URL is never exposed to the browser in production.
 */

import { env } from "@/config/env";

// In the browser we go through the Next.js rewrite proxy.
// On the server (SSR / API routes) we call the backend directly.
const BASE =
  typeof window === "undefined"
    ? env.apiBaseUrl
    : "/api/backend";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly requestId?: string,
  ) {
    super(`API Error ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  tenantId?: string;
  userId?: string;
  timeout?: number;
}

async function request<T>(
  path: string,
  {
    body,
    tenantId = env.defaultTenantId,
    userId,
    timeout = 60_000,
    ...init
  }: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        "X-Tenant-ID": tenantId,
        ...(userId ? { "X-User-ID": userId } : {}),
        ...init.headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      let detail = res.statusText;
      try {
        const json = await res.json();
        detail = json?.detail ?? detail;
      } catch {}
      throw new ApiError(
        res.status,
        detail,
        res.headers.get("X-Request-ID") ?? undefined,
      );
    }

    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

export const apiClient = {
  get: <T>(path: string, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: "GET" }),

  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: "POST", body }),

  delete: <T>(path: string, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: "DELETE" }),
};
