import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Build full API URL using NEXT_PUBLIC_BACKEND_ORIGIN when provided
export function apiUrl(path: string): string {
  const base = process.env.NEXT_PUBLIC_BACKEND_ORIGIN
  if (!base) return path
  try {
    return new URL(path, base).toString()
  } catch {
    return path
  }
}
