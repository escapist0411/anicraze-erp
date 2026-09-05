import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { dashboardPathFor } from '@/lib/roles';
import { LoadingScreen } from '@/components/common/LoadingScreen';
export function PublicOnlyRoute() { const { user, isRestoring } = useAuth(); if (isRestoring) return <LoadingScreen />; return user ? <Navigate to={dashboardPathFor(user.role)} replace /> : <Outlet />; }
