import type { AuthSession } from '@/types/auth';

const SESSION_KEY = 'anicraze.erp.session';

export const sessionStorage = {
  read(): AuthSession | null {
    try {
      const raw = localStorage.getItem(SESSION_KEY) ?? window.sessionStorage.getItem(SESSION_KEY);
      return raw ? (JSON.parse(raw) as AuthSession) : null;
    } catch { return null; }
  },
  write(session: AuthSession) {
    const value=JSON.stringify(session);
    try { (session.rememberMe ? localStorage : window.sessionStorage).setItem(SESSION_KEY,value); }
    catch { window.sessionStorage.setItem(SESSION_KEY,value); }
  },
  clear() { try { localStorage.removeItem(SESSION_KEY); } catch { /* unavailable storage */ } try { window.sessionStorage.removeItem(SESSION_KEY); } catch { /* unavailable storage */ } },
};
