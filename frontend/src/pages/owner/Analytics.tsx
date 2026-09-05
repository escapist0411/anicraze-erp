import { useQuery } from '@tanstack/react-query';
import { RevenueChart } from '@/components/dashboard/RevenueChart';
import { StorePerformance } from '@/components/dashboard/StorePerformance';
import { ProductsTable } from '@/components/dashboard/ProductsTable';
import { dashboardService } from '@/services/dashboard.service';
import { queryKeys } from '@/lib/query-keys';
export default function Analytics(){const query=useQuery({queryKey:queryKeys.dashboard({preset:'THIS_MONTH',view:'analytics'}),queryFn:()=>dashboardService.owner({preset:'THIS_MONTH'})});if(query.isPending)return <div className="h-96 animate-pulse rounded-xl bg-muted"/>;if(query.isError)return <button onClick={()=>query.refetch()} className="rounded-xl border p-6">Analytics failed to load. Retry</button>;const data=query.data;return <div className="mx-auto max-w-[1680px] space-y-6"><div><p className="text-sm text-muted-foreground">Business intelligence</p><h2 className="mt-1 text-3xl font-semibold">Executive analytics</h2></div><RevenueChart data={data.sales_trend.map(x=>({label:x.date,revenue:Number(x.revenue),profit:0,orders:x.orders}))}/><StorePerformance stores={data.store_performance}/><ProductsTable products={data.top_selling_products}/></div>}
