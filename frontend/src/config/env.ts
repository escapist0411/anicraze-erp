const raw = import.meta.env;

function required(name: string, value: string | undefined): string {
  if (!value?.trim()) throw new Error(`Missing required environment variable: ${name}`);
  return value.replace(/\/$/, '');
}

export const env = {
  apiBaseUrl: raw.VITE_API_URL
    ? `${required('VITE_API_URL', raw.VITE_API_URL).replace(/\/api\/v1$/, '')}/api/v1`
    : required('VITE_API_BASE_URL', raw.VITE_API_BASE_URL),
  appName: raw.VITE_APP_NAME || 'ANICRAZE ERP',
  appEnv: raw.VITE_APP_ENV || 'development',
  showDemoCredentials: raw.VITE_SHOW_DEMO_CREDENTIALS === 'true',
} as const;
