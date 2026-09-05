export interface ApiResponse<T> { success: boolean; data: T; message: string | null; timestamp: string }
export interface ApiErrorBody { success?: false; message?: string; error?: { code?: string; details?: Record<string, unknown>; request_id?: string } }
export interface Page<T> { items: T[]; page: number; page_size: number; total: number; pages: number }
export type QueryParams = Record<string, string | number | boolean | undefined | null>;
