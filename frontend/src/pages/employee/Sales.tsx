import { useQuery } from '@tanstack/react-query';
import { ArrowRight, ReceiptText, ShoppingBag } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { formatCurrency, formatDateTime } from '@/lib/format';
import { posService } from '@/services/billing';

export default function Sales() {
  const { user } = useAuth();
  const base = `/${user?.role || 'employee'}`;
  const query = useQuery({ queryKey: ['invoices', 'sales-page'], queryFn: posService.invoices });
  const invoices = query.data || [];
  const completed = invoices.filter(invoice => invoice.invoice_status === 'COMPLETED');
  const today = new Date().toDateString();
  const todaySales = completed.filter(invoice => new Date(invoice.created_at).toDateString() === today);
  const total = completed.reduce((sum, invoice) => sum + Number(invoice.grand_total), 0);
  const todayTotal = todaySales.reduce((sum, invoice) => sum + Number(invoice.grand_total), 0);
  const units = completed.reduce((sum, invoice) => sum + invoice.items.reduce((count, item) => count + item.quantity, 0), 0);

  if (query.isPending) return <div className="h-72 animate-pulse rounded-xl bg-muted" />;
  if (query.isError) return <button onClick={() => query.refetch()} className="rounded-xl border p-6">Sales could not be loaded. Retry</button>;

  return <div className="mx-auto max-w-6xl space-y-5">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-primary">{user?.assignedStoreId ? 'My shop' : 'Authorized shops'}</p><h1 className="mt-1 text-3xl font-semibold">Sales</h1><p className="mt-2 text-sm text-muted-foreground">Completed billing activity available to your account.</p></div>
      <Link to={`${base}/pos`} className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground"><ShoppingBag className="size-4"/>New Sale<ArrowRight className="size-4"/></Link>
    </header>
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Metric label="Today's sales" value={formatCurrency(todayTotal)}/><Metric label="Today's bills" value={todaySales.length}/><Metric label="Total sales" value={formatCurrency(total)}/><Metric label="Units sold" value={units}/>
    </section>
    <section className="overflow-hidden rounded-xl border bg-card">
      <div className="flex items-center justify-between border-b p-4"><div><h2 className="font-semibold">Recent sales</h2><p className="text-xs text-muted-foreground">Completed invoices only</p></div><Link to={`${base}/invoices`} className="text-sm font-semibold text-primary">View all invoices</Link></div>
      <div className="divide-y">{completed.slice(0, 20).map(invoice => <Link key={invoice.id} to={`${base}/invoices`} className="grid gap-2 p-4 hover:bg-muted/30 sm:grid-cols-[1fr_180px_110px_130px] sm:items-center"><span><strong className="block text-sm">{invoice.invoice_number}</strong><span className="text-xs text-muted-foreground">{invoice.customer_name}</span></span><span className="text-xs text-muted-foreground">{formatDateTime(invoice.created_at)}</span><span className="text-xs">{invoice.items.reduce((sum,item)=>sum+item.quantity,0)} units</span><strong className="sm:text-right">{formatCurrency(invoice.grand_total)}</strong></Link>)}</div>
      {!completed.length && <div className="p-10 text-center"><ReceiptText className="mx-auto size-8 text-muted-foreground"/><p className="mt-3 text-sm font-semibold">No completed sales yet</p></div>}
    </section>
  </div>;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <article className="rounded-xl border bg-card p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-xl font-bold">{value}</p></article>;
}
