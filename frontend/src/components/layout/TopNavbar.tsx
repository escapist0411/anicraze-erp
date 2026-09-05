import { Bell, Menu, Moon, Search, Sun } from 'lucide-react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTheme } from '@/hooks/useTheme';
import { roleLabels } from '@/lib/roles';
import type { User } from '@/types/auth';
import { notificationsService } from '@/services/notifications';

const pageNames: Record<string, string> = {
  dashboard: 'Dashboard',
  analytics: 'Analytics',
  inventory: 'Inventory',
  products: 'Products',
  finance: 'Finance',
  reports: 'Reports',
  stores: 'Stores',
  employees: 'Employees',
  notifications: 'Notifications',
  settings: 'Settings',
};

export function TopNavbar({ user, onOpenMobile }: { user: User; onOpenMobile: () => void }) {
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const pathParts = useLocation().pathname.split('/');
  const segment = pathParts[pathParts.length - 1] || 'dashboard';
  const title = pageNames[segment] ?? 'Workspace';
  const initials = user.name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
  const [notificationsOpen,setNotificationsOpen]=useState(false);
  const notifications=useQuery({queryKey:['notifications','summary'],queryFn:notificationsService.summary,refetchInterval:60_000,staleTime:30_000,enabled:user.role!=='employee'});
  const openNotification=(path?:string)=>{setNotificationsOpen(false);navigate(`/${user.role}/${path||'notifications'}`)};

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full min-w-0 shrink-0 items-center gap-2 border-b bg-background/90 px-3 backdrop-blur-xl sm:h-18 sm:gap-3 sm:px-5 lg:h-20 lg:px-6">
      <button
        type="button"
        className="grid size-9 shrink-0 place-items-center rounded-lg hover:bg-muted lg:hidden"
        onClick={onOpenMobile}
        aria-label="Open menu"
      >
        <Menu className="size-5" />
      </button>

      <div className="min-w-0 shrink">
        <p className="hidden truncate text-xs text-muted-foreground sm:block">Workspace / <span className="text-foreground">{title}</span></p>
        <h1 className="truncate text-base font-semibold tracking-tight sm:text-lg">{title}</h1>
      </div>

      <label className="ml-auto hidden min-w-0 flex-1 items-center rounded-lg border bg-card px-3 sm:flex sm:max-w-sm">
        <Search className="size-4 shrink-0 text-muted-foreground" />
        <input
          disabled
          title="Global search is not available in this deployment."
          className="h-10 min-w-0 flex-1 bg-transparent px-2 text-sm outline-none placeholder:text-muted-foreground"
          placeholder="Global search unavailable"
        />
      </label>

      <button
        type="button"
        className="hidden size-10 shrink-0 place-items-center rounded-lg border bg-card hover:bg-muted sm:grid"
        onClick={toggleTheme}
        aria-label="Toggle color mode"
      >
        {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </button>
      {user.role!=='employee'&&<div className="relative"><button type="button" onClick={()=>setNotificationsOpen(value=>!value)} className="relative grid size-10 shrink-0 place-items-center rounded-lg border bg-card hover:bg-muted" aria-label="Open notifications" aria-expanded={notificationsOpen}>
        <Bell className="size-4" />{(notifications.data?.unread_count??0)>0&&<span className="absolute -right-1 -top-1 grid min-w-5 place-items-center rounded-full bg-destructive px-1 text-[10px] font-bold text-white">{Math.min(notifications.data?.unread_count??0,99)}</span>}
      </button>{notificationsOpen&&<div className="absolute right-0 top-12 z-50 w-[min(22rem,calc(100vw-1.5rem))] rounded-xl border bg-card p-3 shadow-xl"><div className="flex items-center justify-between px-1"><h2 className="font-semibold">Notifications</h2><span className="text-xs text-muted-foreground">{notifications.data?.unread_count??0} unread</span></div><div className="mt-3 space-y-2">{notifications.isPending?<div className="h-24 animate-pulse rounded-lg bg-muted"/>:(notifications.data?.recent??[]).map(item=><button key={item.id} onClick={()=>openNotification(item.action_path)} className="block w-full rounded-lg border p-3 text-left hover:bg-muted"><span className="text-xs font-semibold">{item.title}</span><p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.message}</p><time className="mt-1 block text-[10px] text-muted-foreground">{new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(item.created_at))}</time></button>)}{!notifications.isPending&&!notifications.data?.recent.length&&<p className="py-6 text-center text-sm text-muted-foreground">No active notifications.</p>}</div><button onClick={()=>openNotification()} className="mt-3 w-full rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground">View all</button></div>}</div>}
      <div className="ml-1 flex min-w-0 shrink-0 items-center gap-2">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">{initials}</span>
        <div className="hidden min-w-0 leading-tight xl:block">
          <p className="truncate text-sm font-medium">{user.name}</p>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{roleLabels[user.role]}</p>
        </div>
      </div>
    </header>
  );
}
