import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
export function PermissionRoute({permission}:{permission:string}){const{user}=useAuth();if(!user)return <Navigate to="/login" replace/>;return user.permissions.includes('*')||user.permissions.includes(permission)?<Outlet/>:<Navigate to="/forbidden" replace/>;}
