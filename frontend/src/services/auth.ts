import { api } from './api';
import type { AuthSession, LoginPayload, Role, User } from '@/types/auth';

import type { ApiResponse } from '@/types/api';

interface BackendUser {
  id: string;
  name: string;
  email: string;
  avatar_url: string | null;
  roles: string[];
  permissions: string[];
  assigned_store_id: string | null;
}

interface BackendLoginResponse {
  access_token: string;
  refresh_token: string;
  user: BackendUser;
}

interface BackendRefreshResponse {
  access_token: string;
  refresh_token: string;
}

function roleFor(roles: string[]): Role {
  if (roles.includes('OWNER') || roles.includes('ADMIN')) return 'owner';
  if (roles.includes('MANAGER')) return 'manager';
  return 'employee';
}

function toUser(user: BackendUser): User {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: roleFor(user.roles),
    roles: user.roles,
    permissions: user.permissions,
    assignedStoreId: user.assigned_store_id ?? undefined,
    avatarUrl: user.avatar_url ?? undefined,
  };
}

export const authService = {
  async forgotPassword(email: string): Promise<string> {
    const { data } = await api.post<ApiResponse<unknown>>('/auth/forgot-password', { email });
    return data.message ?? 'If an account exists for this email, password reset instructions have been sent.';
  },

  async resetPassword(token: string, password: string): Promise<string> {
    const { data } = await api.post<ApiResponse<unknown>>('/auth/reset-password', { token, password });
    return data.message ?? 'Password reset successfully.';
  },

  async login(payload: LoginPayload): Promise<AuthSession> {
    const { data } = await api.post<ApiResponse<BackendLoginResponse>>('/auth/login', {
      email: payload.email,
      password: payload.password,
      remember_me: payload.rememberMe,
    });
    return {
      accessToken: data.data.access_token,
      refreshToken: data.data.refresh_token,
      user: toUser(data.data.user),
      rememberMe: payload.rememberMe,
    };
  },

  async me(): Promise<User> {
    const { data } = await api.get<ApiResponse<BackendUser>>('/auth/me');
    return toUser(data.data);
  },

  async logout(refreshToken?: string): Promise<void> {
    if (!refreshToken) return;
    await api.post('/auth/logout', { refresh_token: refreshToken });
  },

  async refresh(refreshToken: string, user: User): Promise<AuthSession> {
    const { data } = await api.post<ApiResponse<BackendRefreshResponse>>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return {
      accessToken: data.data.access_token,
      refreshToken: data.data.refresh_token,
      user,
    };
  },
};
