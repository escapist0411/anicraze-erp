import { Store } from 'lucide-react';
import { formatCurrency } from '@/lib/format';
import type { StorePerformancePoint } from '@/types/dashboard';

export function StorePerformance({stores=[]}:{stores?:StorePerformancePoint[]}){
 return <section className="rounded-xl border bg-card p-5 shadow-sm"><h3 className="font-semibold">Store performance</h3><p className="mt-1 text-xs text-muted-foreground">Completed sales by location</p>{stores.length?<div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{stores.map((store,index)=><article key={store.store_id} className="rounded-xl border bg-muted/25 p-3.5"><span className="grid size-9 place-items-center rounded-lg bg-indigo-500 text-white"><Store className="size-4"/></span><h4 className="mt-4 truncate text-sm font-semibold" title={store.store_name}>{store.store_name||`Store ${index+1}`}</h4><p className="mt-3 text-xs text-muted-foreground">Net sales</p><p className="font-semibold">{formatCurrency(store.net_sales)}</p><p className="mt-2 text-xs text-muted-foreground">{store.orders} orders · AOV {formatCurrency(store.average_order_value)}</p></article>)}</div>:<p className="mt-6 text-sm text-muted-foreground">No store sales found for this period.</p>}</section>
}
