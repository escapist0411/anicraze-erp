import axios from 'axios';
import type { ApiErrorBody } from '@/types/api';

export class ApiError extends Error {
  constructor(message: string, public status?: number, public code?: string, public details?: Record<string, unknown>) { super(message); this.name = 'ApiError'; }
}
export function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const body = error.response?.data;
    return new ApiError(body?.message || (error.response ? 'The request could not be completed.' : 'Cannot reach the ERP server.'), error.response?.status, body?.error?.code, body?.error?.details);
  }
  return new ApiError(error instanceof Error ? error.message : 'An unexpected error occurred.');
}
export const getApiErrorMessage = (error: unknown) => normalizeApiError(error).message;
export function mapValidationErrors(error: unknown): Record<string, string> {
  const details = normalizeApiError(error).details; const fields = details?.fields;
  return fields && typeof fields === 'object' ? fields as Record<string, string> : {};
}
