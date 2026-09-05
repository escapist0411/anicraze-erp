import axios, { type AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';
import { env } from '@/config/env';
import { normalizeApiError } from '@/lib/api-error';
import { sessionStorage } from '@/lib/storage';
import type { ApiResponse, QueryParams } from '@/types/api';

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };
interface RefreshPayload { access_token: string; refresh_token: string }

export const api = axios.create({ baseURL: env.apiBaseUrl, timeout: 15_000, headers: { Accept: 'application/json', 'Content-Type': 'application/json' } });
const refreshClient = axios.create({ baseURL: env.apiBaseUrl, timeout: 15_000, headers: { 'Content-Type': 'application/json' } });
let refreshPromise: Promise<string> | null = null;

api.interceptors.request.use((config) => {
  const token = sessionStorage.read()?.accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

async function refreshAccessToken(): Promise<string> {
  const current = sessionStorage.read();
  if (!current?.refreshToken) throw new Error('No refresh token');
  const response = await refreshClient.post<ApiResponse<RefreshPayload>>('/auth/refresh', { refresh_token: current.refreshToken });
  const next = { ...current, accessToken: response.data.data.access_token, refreshToken: response.data.data.refresh_token };
  sessionStorage.write(next);
  window.dispatchEvent(new CustomEvent('anicraze:session-refreshed', { detail: next }));
  return next.accessToken;
}

api.interceptors.response.use((response) => response, async (error: AxiosError) => {
  const config = error.config as RetryConfig | undefined;
  const isAuthRoute = config?.url?.includes('/auth/login') || config?.url?.includes('/auth/refresh');
  if (error.response?.status === 401 && config && !config._retry && !isAuthRoute) {
    config._retry = true;
    try {
      refreshPromise ??= refreshAccessToken().finally(() => { refreshPromise = null; });
      config.headers.Authorization = `Bearer ${await refreshPromise}`;
      return api(config);
    } catch {
      sessionStorage.clear(); window.dispatchEvent(new Event('anicraze:session-expired'));
    }
  }
  return Promise.reject(normalizeApiError(error));
});

export async function getData<T>(url: string, params?: QueryParams, config?: AxiosRequestConfig): Promise<T> {
  return (await api.get<ApiResponse<T>>(url, { ...config, params })).data.data;
}
export async function downloadFile(url: string, params?: QueryParams, config?: AxiosRequestConfig): Promise<void> {
  const response = await api.get<Blob>(url, { ...config, params, responseType: 'blob' });
  const disposition = response.headers['content-disposition'] as string | undefined;
  const filename = disposition?.match(/filename="?([^";]+)"?/i)?.[1] ?? 'ANICRAZE-export';
  const href = URL.createObjectURL(response.data); const anchor = document.createElement('a'); anchor.href=href; anchor.download=filename; anchor.click(); URL.revokeObjectURL(href);
}
export async function uploadFile<T>(url: string, form: FormData): Promise<T> {
  return (await api.post<ApiResponse<T>>(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })).data.data;
}
