import { useAuth } from '@/hooks/useAuth';

function matches(granted: string, required: string) {
  if (granted === '*' || granted === required) return true;
  return granted.endsWith('.*') && required.startsWith(granted.slice(0, -1));
}

export function usePermission(required: string | string[], mode: 'any' | 'all' = 'all') {
  const { user } = useAuth();
  const needs = Array.isArray(required) ? required : [required];
  const permissions = user?.permissions ?? [];
  if (!needs.length) return true;
  const checks = needs.map((need) => permissions.some((granted) => matches(granted, need)));
  return mode === 'any' ? checks.some(Boolean) : checks.every(Boolean);
}
