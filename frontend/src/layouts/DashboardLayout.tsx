import { useState, useSyncExternalStore } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { AppFooter } from '@/components/layout/AppFooter';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopNavbar } from '@/components/layout/TopNavbar';
import { useAuth } from '@/hooks/useAuth';

const DESKTOP_MEDIA_QUERY = '(min-width: 1024px)';

function subscribeToDesktopViewport(onChange: () => void) {
  const mediaQuery = window.matchMedia(DESKTOP_MEDIA_QUERY);
  mediaQuery.addEventListener('change', onChange);
  return () => mediaQuery.removeEventListener('change', onChange);
}

function getDesktopViewportSnapshot() {
  return window.matchMedia(DESKTOP_MEDIA_QUERY).matches;
}

function useDesktopViewport() {
  return useSyncExternalStore(subscribeToDesktopViewport, getDesktopViewportSnapshot, () => true);
}

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const isDesktopViewport = useDesktopViewport();

  if (!user) return null;

  const signOut = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="flex h-dvh w-full max-w-full overflow-hidden bg-muted/30">
      <Sidebar
        role={user.role}
        permissions={user.permissions}
        collapsed={!isDesktopViewport || collapsed}
        mobileOpen={mobileOpen}
        onToggle={() => setCollapsed((value) => !value)}
        onCloseMobile={() => setMobileOpen(false)}
        onLogout={signOut}
      />

      <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <TopNavbar user={user} onOpenMobile={() => setMobileOpen(true)} />
        <main className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain">
          <div className="flex min-h-full w-full min-w-0 max-w-full flex-col">
            <div className="w-full min-w-0 max-w-full flex-1 px-4 py-4 sm:px-5 sm:py-5 lg:px-6 lg:py-6 2xl:px-8">
              <Outlet />
            </div>
            <AppFooter />
          </div>
        </main>
      </section>
    </div>
  );
}
