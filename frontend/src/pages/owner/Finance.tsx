import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Download} from 'lucide-react';
import {reportsService} from '@/services/reports';
import {inventoryService} from '@/services/inventory';
import {queryKeys} from '@/lib/query-keys';
import {getApiErrorMessage} from '@/lib/api-error';

type Money=string|number;
type Row={store_id:string;shop:string;gross_sales:Money;discounts:Money;net_sales:Money;returns_refunds:Money;net_revenue:Money;cogs:Money;gross_profit:Money;gross_margin_percentage:Money};
type FinanceData={summary:Omit<Row,'store_id'|'shop'>;rows:Row[]};
const money=(value:Money)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(Number(value));

export default function Finance(){
 const[preset,setPreset]=useState('THIS_MONTH'),[storeId,setStoreId]=useState(''),[exporting,setExporting]=useState(false),[exportError,setExportError]=useState('');
 const params={preset,...(storeId?{store_id:storeId}:{})};
 const stores=useQuery({queryKey:['stores'],queryFn:inventoryService.stores});
 const query=useQuery({queryKey:queryKeys.reports('finance-shop-profit-loss',params),queryFn:()=>reportsService.get('finance','shop-profit-loss',params) as Promise<unknown> as Promise<FinanceData>});
 const exportPdf=async()=>{setExporting(true);setExportError('');try{await reportsService.export('finance_shop-profit-loss','PDF',params)}catch(error){setExportError(getApiErrorMessage(error))}finally{setExporting(false)}};
 if(query.isPending)return <div className="h-72 animate-pulse rounded-xl bg-muted"/>;
 if(query.isError)return <button onClick={()=>query.refetch()} className="rounded-xl border p-6">Finance report failed to load. Retry</button>;
 const{summary,rows}=query.data,cards=[['Net Revenue',summary.net_revenue],['Cost of Goods Sold',summary.cogs],['Gross Profit',summary.gross_profit],['Gross Margin',`${Number(summary.gross_margin_percentage).toFixed(2)}%`]];
 return <div className="mx-auto max-w-[1680px] space-y-6"><header className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-sm text-muted-foreground">Owner-only financial reporting</p><h1 className="mt-1 text-3xl font-semibold">Shop-wise Profit &amp; Loss</h1><p className="mt-1 text-sm text-muted-foreground">COGS uses the purchase-cost snapshot captured at the time of sale.</p></div><div className="flex flex-wrap gap-2"><select aria-label="Shop" value={storeId} onChange={event=>setStoreId(event.target.value)} className="h-11 rounded-lg border bg-background px-3"><option value="">All Shops</option>{stores.data?.map(store=><option key={store.id} value={store.id}>{store.name}</option>)}</select><select aria-label="Date range" value={preset} onChange={event=>setPreset(event.target.value)} className="h-11 rounded-lg border bg-background px-3"><option value="TODAY">Today</option><option value="THIS_WEEK">This week</option><option value="THIS_MONTH">This month</option><option value="LAST_MONTH">Last month</option><option value="THIS_YEAR">This year</option></select><button onClick={exportPdf} disabled={exporting} className="inline-flex h-11 items-center gap-2 rounded-lg border bg-card px-4 text-sm font-semibold disabled:opacity-50"><Download className="size-4"/>{exporting?'Exporting…':'Export PDF'}</button></div></header>{exportError&&<p role="alert" className="text-sm text-destructive">{exportError}</p>}<section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label,value])=><article key={String(label)} className="rounded-xl border bg-card p-5"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold">{typeof value==='string'&&value.endsWith('%')?value:money(value)}</p></article>)}</section><section className="overflow-x-auto rounded-xl border bg-card"><table className="w-full min-w-[980px] text-sm"><thead className="bg-muted/60 text-left"><tr>{['Shop','Gross sales','Discounts','Net sales','Returns','Net revenue','COGS','Gross profit','Margin'].map(x=><th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.store_id} className="border-t"><td className="px-4 py-3 font-semibold">{row.shop}</td>{(['gross_sales','discounts','net_sales','returns_refunds','net_revenue','cogs','gross_profit'] as const).map(key=><td key={key} className="px-4 py-3">{money(row[key])}</td>)}<td className="px-4 py-3">{Number(row.gross_margin_percentage).toFixed(2)}%</td></tr>)}</tbody></table>{!rows.length&&<p className="p-8 text-center text-muted-foreground">No completed sales in this period.</p>}</section></div>;
}
