export const ROLE_KEYS = ['owner', 'manager', 'employee'] as const;
export type Role = (typeof ROLE_KEYS)[number];

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  roles: string[];
  permissions: string[];
  assignedStoreId?: string;
  avatarUrl?: string;
}

export interface AuthSession {
  accessToken: string;
  refreshToken?: string;
  user: User;
  rememberMe?: boolean;
}

export interface LoginPayload {
  email: string;
  password: string;
  rememberMe: boolean;
}
