import { createContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { authService } from '@/services/auth';
import { sessionStorage } from '@/lib/storage';
import type { AuthSession, LoginPayload, User } from '@/types/auth';

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isRestoring: boolean;
  login: (payload: LoginPayload) => Promise<User>;
  logout: () => Promise<void>;
}
export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  useEffect(() => {
    const restore=async()=>{const saved=sessionStorage.read();if(!saved){setIsRestoring(false);return;}try{const user=await authService.me();const next={...saved,user};sessionStorage.write(next);setSession(next);}catch{sessionStorage.clear();}finally{setIsRestoring(false);}};void restore();
    const refreshed=(event:Event)=>setSession((event as CustomEvent<AuthSession>).detail);
    const expired=()=>setSession(null);
    window.addEventListener('anicraze:session-refreshed',refreshed);window.addEventListener('anicraze:session-expired',expired);
    return()=>{window.removeEventListener('anicraze:session-refreshed',refreshed);window.removeEventListener('anicraze:session-expired',expired);};
  }, []);
  const login = async (payload: LoginPayload) => {
    const nextSession = await authService.login(payload);
    setSession(nextSession); sessionStorage.write(nextSession);
    return nextSession.user;
  };
  const logout = async () => { await authService.logout(session?.refreshToken).catch(() => undefined); sessionStorage.clear(); setSession(null); };
  const value = useMemo(() => ({ user: session?.user ?? null, isAuthenticated: Boolean(session), isRestoring, login, logout }), [session, isRestoring]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
