import { motion } from 'framer-motion';
import { FileBarChart, FilePlus2, PackagePlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

const actions = [
  { label: 'Products', icon: PackagePlus, path: 'products' },
  { label: 'Create invoice', icon: FilePlus2, path: 'billing', unavailable: true },
  { label: 'Generate report', icon: FileBarChart, path: 'reports' },
];

export function DashboardHeader() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = user?.role ?? 'owner';
  const today = new Intl.DateTimeFormat('en-IN', { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date());
  return <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
    <div><p className="text-sm font-medium text-muted-foreground">{today}</p><h2 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Good morning, {user?.name?.split(' ')[0] ?? 'there'} <span className="inline-block origin-bottom animate-[wave_2s_ease-in-out_infinite]">👋</span></h2><p className="mt-2 text-sm text-muted-foreground">Here is your live operational view.</p></div>
    <div className="flex flex-wrap gap-2">{actions.map(({ label, icon: Icon, path, unavailable }, index) => <button key={label} type="button" disabled={unavailable} title={unavailable ? 'Invoice creation is not available in this deployment.' : undefined} onClick={() => !unavailable && navigate(`/${role}/${path}`)} className={`inline-flex h-10 items-center gap-2 rounded-lg px-3.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${index === 0 ? 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90' : 'border bg-card hover:bg-muted'}`}><Icon className="size-4" />{label}</button>)}</div>
  </motion.section>;
}
