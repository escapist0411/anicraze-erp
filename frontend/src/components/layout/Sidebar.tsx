import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  BarChart3,
  Bell,
  Boxes,
  Building2,
  ChevronLeft,
  ChevronRight,
  FileText,
  ReceiptText,
  ShoppingBag,
  LayoutDashboard,
  LogOut,
  Package,
  PackagePlus,
  ScanLine,
  Settings,
  Store,
  Users,
  Wallet,
  ArrowRightLeft,
  X,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useEffect, useRef } from 'react';
import { BrandMark } from '@/components/auth/BrandMark';
import { cn } from '@/lib/utils';
import type { Role } from '@/types/auth';
import type { NavigationItem } from '@/types/navigation';
import { SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_EXPANDED_WIDTH } from './sidebarDimensions';

const allRoles: Role[] = ['owner', 'manager', 'employee'];
const navigation: NavigationItem[] = [
  { label: 'Dashboard', to: 'dashboard', icon: LayoutDashboard, roles: allRoles },
  { label: 'Scan & Bill', to: 'pos', icon: ReceiptText, roles: allRoles, permission: 'billing.create' },
  { label: 'Sales', to: 'sales', icon: ShoppingBag, roles: allRoles, permission: 'billing.read' },
  { label: 'Invoices', to: 'invoices', icon: FileText, roles: allRoles, permission: 'billing.read' },
  { label: 'Analytics', to: 'analytics', icon: BarChart3, roles: ['owner', 'manager'] },
  { label: 'Inward Stock', to: 'receive-stock', icon: PackagePlus, roles: ['owner','manager'], permission: 'inventory.create' },
  { label: 'Barcode Centre', to: 'barcodes', icon: Package, roles: ['owner','manager'], permission: 'products.manage_barcode' },
  { label: 'Scan to Godown', to: 'godown-intake', icon: ScanLine, roles: ['owner','manager'], permission: 'inventory.create' },
  { label: 'Divert Stock', to: 'divert-stock', icon: ArrowRightLeft, roles: ['owner','manager'], permission: 'inventory.transfer' },
  { label: 'Inventory', to: 'inventory', icon: Boxes, roles: ['owner','manager'], permission: 'inventory.read' },
  { label: 'Products', to: 'products', icon: Package, roles: allRoles, permission: 'products.read' },
  { label: 'Finance', to: 'finance', icon: Wallet, roles: ['owner'], permission: 'reports.finance.read' },
  { label: 'Payments', to: 'payments', icon: Wallet, roles: ['owner'] },
  { label: 'Reports', to: 'reports', icon: FileText, roles: ['owner', 'manager'], permission: 'reports.sales.read' },
  { label: 'Stores', to: 'stores', icon: Store, roles: ['owner', 'manager'], permission: 'stores.read' },
  { label: 'Employees', to: 'employees', icon: Users, roles: ['owner', 'manager'], permission: 'employees.read' },
  { label: 'Notifications', to: 'notifications', icon: Bell, roles: ['owner','manager'] },
  { label: 'Settings', to: 'settings', icon: Settings, roles: allRoles },
];

interface SidebarProps {
  role: Role;
  permissions: string[];
  collapsed: boolean;
  mobileOpen: boolean;
  onToggle: () => void;
  onCloseMobile: () => void;
  onLogout: () => void;
}

interface SidebarPanelProps {
  role: Role;
  permissions: string[];
  collapsed: boolean;
  mobile: boolean;
  onToggle: () => void;
  onCloseMobile: () => void;
  onLogout: () => void;
}

function SidebarPanel({ role, permissions, collapsed, mobile, onToggle, onCloseMobile, onLogout }: SidebarPanelProps) {
  const panelRef=useRef<HTMLElement>(null);
  useEffect(()=>{if(!mobile)return;const panel=panelRef.current;panel?.focus();const keydown=(event:KeyboardEvent)=>{if(event.key==='Escape')onCloseMobile();if(event.key==='Tab'&&panel){const items=[...panel.querySelectorAll<HTMLElement>('a,button,input,select,[tabindex]:not([tabindex="-1"])')].filter(x=>!x.hasAttribute('disabled'));if(!items.length)return;const first=items[0],last=items[items.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}};document.addEventListener('keydown',keydown);return()=>document.removeEventListener('keydown',keydown);},[mobile,onCloseMobile]);
  const visible = navigation.filter((item) => item.roles.includes(role) && (!item.permission || permissions.includes('*') || permissions.includes(item.permission)));
  const base = `/${role}`;
  const reduceMotion = useReducedMotion();
  const width = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH;

  return (
    <motion.aside
      ref={panelRef}
      role={mobile?'dialog':undefined}
      aria-modal={mobile||undefined}
      aria-label={mobile?'Main navigation':undefined}
      tabIndex={mobile?-1:undefined}
      initial={false}
      animate={mobile ? undefined : { width }}
      style={mobile ? { width: 'min(280px, 85vw)' } : undefined}
      transition={reduceMotion ? { duration: 0 } : { duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
      className={cn(
        'h-dvh shrink-0 flex-col overflow-hidden border-r bg-card text-card-foreground',
        mobile ? 'flex shadow-2xl' : 'hidden md:flex',
      )}
    >
      <header className={cn('flex h-20 shrink-0 items-center border-b', collapsed ? 'justify-center px-3' : 'px-5')}>
        {collapsed ? (
          <span className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Building2 className="size-5" />
          </span>
        ) : (
          <BrandMark />
        )}
        {mobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="ml-auto grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
            aria-label="Close menu"
          >
            <X className="size-5" />
          </button>
        )}
      </header>

      <nav className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain px-3 py-4">
        {!collapsed && (
          <p className="mb-2 px-3 text-[10px] font-bold tracking-[0.16em] text-muted-foreground uppercase">Workspace</p>
        )}
        <div className="space-y-1">
          {visible.map(({ label, to, icon: Icon }) => (
            <NavLink
              key={to}
              to={`${base}/${to}`}
              onClick={mobile ? onCloseMobile : undefined}
              title={collapsed ? label : undefined}
              className={({ isActive }) => cn(
                'flex h-11 w-full min-w-0 items-center rounded-xl text-sm font-medium transition-colors duration-150',
                collapsed ? 'justify-center px-0' : 'gap-3 px-3',
                isActive
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <Icon className="size-[18px] shrink-0" />
              <AnimatePresence initial={false}>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: reduceMotion ? 0 : 0.15 }}
                    className="truncate"
                  >
                    {label}
                  </motion.span>
                )}
              </AnimatePresence>
            </NavLink>
          ))}
        </div>
      </nav>

      <footer className="shrink-0 border-t p-3">
        <button
          type="button"
          onClick={onLogout}
          title={collapsed ? 'Log out' : undefined}
          className={cn(
            'flex h-11 w-full min-w-0 items-center rounded-xl text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive',
            collapsed ? 'justify-center px-0' : 'gap-3 px-3',
          )}
        >
          <LogOut className="size-[18px] shrink-0" />
          {!collapsed && <span className="truncate">Log out</span>}
        </button>
        {!mobile && (
          <button
            type="button"
            onClick={onToggle}
            className="mt-1 hidden h-10 w-full items-center justify-center rounded-xl text-muted-foreground transition hover:bg-muted hover:text-foreground lg:flex"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
          </button>
        )}
      </footer>
    </motion.aside>
  );
}

export function Sidebar({ role, permissions, collapsed, mobileOpen, onToggle, onCloseMobile, onLogout }: SidebarProps) {
  const reduceMotion = useReducedMotion();

  return (
    <>
      <SidebarPanel
        role={role}
        permissions={permissions}
        collapsed={collapsed}
        mobile={false}
        onToggle={onToggle}
        onCloseMobile={onCloseMobile}
        onLogout={onLogout}
      />

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.button
              type="button"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.2 }}
              onClick={onCloseMobile}
              className="fixed inset-0 z-40 bg-black/50 md:hidden"
              aria-label="Close menu"
            />
            <motion.div
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
              className="fixed inset-y-0 left-0 z-50 md:hidden"
            >
              <SidebarPanel
                role={role}
                permissions={permissions}
                collapsed={false}
                mobile
                onToggle={onToggle}
                onCloseMobile={onCloseMobile}
                onLogout={onLogout}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
