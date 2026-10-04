/** Public navigation only. Never place ERP credentials or backend secrets here. */
const fallbackErpUrl = 'https://erp.anicraze.com';

function approvedUrl(value: string | undefined, fallback: string): string {
  if (!value) return fallback;
  try {
    const parsed = new URL(value);
    if (parsed.protocol === 'https:' && parsed.hostname === 'erp.anicraze.com' &&
        !parsed.username && !parsed.password && !parsed.search && !parsed.hash) {
      return parsed.origin;
    }
  } catch {
    // An invalid public value must not become a clickable URL.
  }
  return fallback;
}

export const ERP_URL = approvedUrl(import.meta.env.VITE_ERP_URL, fallbackErpUrl);

/** Populate only after ANICRAZE confirms the official profile URLs. */
export const SOCIAL_LINKS: ReadonlyArray<{ label: string; url: string }> = [];

/** Optional verified map URLs for permanent locations; event sites stay unset. */
export const STORE_MAP_LINKS: Readonly<Record<string, string>> = {};
