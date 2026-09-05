import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { DashboardHeader } from '@/components/dashboard/DashboardHeader';
import { KpiCard } from '@/components/dashboard/KpiCard';
import { RevenueChart } from '@/components/dashboard/RevenueChart';
import { StorePerformance } from '@/components/dashboard/StorePerformance';
import { ProductsTable } from '@/components/dashboard/ProductsTable';
import { dashboardService } from '@/services/dashboard.service';
import { queryKeys } from '@/lib/query-keys';
import { formatCurrency } from '@/lib/format';
import { getApiErrorMessage } from '@/lib/api-error';
import { useAuth } from '@/hooks/useAuth';

export default function Dashboard() {
  const {user}=useAuth();
  if(user?.role==='employee') return <div className="mx-auto max-w-3xl space-y-6"><DashboardHeader/><section className="rounded-xl border bg-card p-6"><h3 className="font-semibold">Your workspace</h3><p className="mt-2 text-sm text-muted-foreground">Use the navigation to access the operational tools assigned to your role. Company finance and owner analytics are restricted.</p></section></div>;
  return <ManagementDashboard/>;
}

function ManagementDashboard() {
  const query=useQuery({queryKey:queryKeys.dashboard({preset:'THIS_MONTH'}),queryFn:()=>dashboardService.owner({preset:'THIS_MONTH'}),staleTime:60_000});
  if(query.isPending)return <div className="mx-auto max-w-[1680px] space-y-6"><DashboardHeader/><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{Array.from({length:8},(_,i)=><div key={i} className="h-36 animate-pulse rounded-xl border bg-muted"/>)}</div></div>;
  if(query.isError)return <div className="mx-auto max-w-xl rounded-xl border bg-card p-8 text-center"><AlertTriangle className="mx-auto size-8 text-destructive"/><h2 className="mt-3 font-semibold">Dashboard unavailable</h2><p className="mt-2 text-sm text-muted-foreground">{getApiErrorMessage(query.error)}</p><button onClick={()=>query.refetch()} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"><RefreshCw className="size-4"/>Retry</button></div>;
  const data=query.data;const trend=data.sales_trend.map(point=>({label:point.date,revenue:Number(point.revenue),profit:0,orders:point.orders}));
  const kpis=[
    {label:'Net sales (excl. GST)',value:formatCurrency(data.kpis.net_sales),change:'Live',trend:trend.map(x=>x.revenue),tone:'indigo',icon:'revenue'},
    {label:'Estimated operating profit',value:formatCurrency(data.kpis.estimated_net_operating_profit),change:'Live',trend:trend.map(x=>x.revenue),tone:'emerald',icon:'profit'},
    {label:'Inventory value',value:formatCurrency(data.inventory_summary.inventory_value),change:'Live',trend:[data.inventory_summary.available_units],tone:'amber',icon:'inventory'},
    {label:'Orders',value:String(data.kpis.orders),change:'Live',trend:trend.map(x=>x.orders),tone:'rose',icon:'orders'},
    {label:'GST collected',value:formatCurrency(data.kpis.gst_collected),change:'Live',trend:[Number(data.kpis.gst_collected)],tone:'sky',icon:'sales'},
    {label:'Expenses',value:formatCurrency(data.kpis.expenses),change:'Live',trend:[Number(data.kpis.expenses)],tone:'orange',icon:'pending'},
    {label:'Low stock',value:String(data.inventory_summary.low_stock_count),change:'Live',trend:[data.inventory_summary.low_stock_count],tone:'violet',icon:'inventory'},
    {label:'Active employees',value:String(data.active_employees),change:'Live',trend:[data.active_employees],tone:'cyan',icon:'customers'},
  ];
  return <div className="mx-auto max-w-[1680px] space-y-6"><DashboardHeader/><section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{kpis.map((item,index)=><KpiCard key={item.label} item={item} index={index}/>)}</section><RevenueChart data={trend}/><StorePerformance stores={data.store_performance}/><ProductsTable products={data.top_selling_products}/><section className="grid gap-4 lg:grid-cols-2"><div className="rounded-xl border bg-card p-5"><h3 className="font-semibold">Payment mix</h3><div className="mt-3 space-y-2">{data.payment_summary.map(row=><div key={row.payment_method} className="flex justify-between rounded-lg bg-muted/40 p-3 text-sm"><span>{row.payment_method.replace(/_/g,' ')}</span><span className="font-semibold">{formatCurrency(row.amount)} · {row.percentage}%</span></div>)}</div></div><div className="rounded-xl border bg-card p-5"><h3 className="font-semibold">Operational alerts</h3>{data.alerts.length?<ul className="mt-3 space-y-2">{data.alerts.map(alert=><li key={alert.code??alert.message} className="rounded-lg bg-amber-500/10 p-3 text-sm">{alert.message}</li>)}</ul>:<p className="mt-3 text-sm text-muted-foreground">No active alerts.</p>}</div><div className="rounded-xl border bg-card p-5"><h3 className="font-semibold">Business insights</h3>{data.business_insights.map(insight=><p key={insight.message} className="mt-3 text-sm text-muted-foreground">{insight.message}</p>)}</div><div className="rounded-xl border bg-card p-5"><h3 className="font-semibold">Financial definitions</h3>{Object.values(data.definitions).map(text=><p key={text} className="mt-2 text-xs text-muted-foreground">{text}</p>)}</div></section></div>;
}
