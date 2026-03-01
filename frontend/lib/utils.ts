import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatPercent(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

export function formatCost(usd: number): string {
  return usd < 0.01 ? `<$0.01` : `$${usd.toFixed(4)}`;
}

export function truncateId(id: string, chars = 8): string {
  return `${id.slice(0, chars)}…`;
}

export function validatePatientId(value: string): string | null {
  if (!value) return "Patient ID is required.";
  if (!/^\d+$/.test(value)) return "Patient ID must contain only digits.";
  if (value.length < 7 || value.length > 8)
    return "Patient ID must be 7 or 8 digits.";
  return null;
}
