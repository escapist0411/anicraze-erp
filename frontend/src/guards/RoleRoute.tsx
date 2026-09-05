import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { dashboardPathFor } from '@/lib/roles';
import type { Role } from '@/types/auth';

export function RoleRoute({ role }: { role: Role }) {
  const { user } = useAuth();
  return user?.role === role ? <Outlet /> : <Navigate to={user ? dashboardPathFor(user.role) : '/login'} replace />;
}
