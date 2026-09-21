import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, LoaderCircle, Printer, RefreshCw, Send } from 'lucide-react';
import { reportsService } from '@/services/reports';
import { getApiErrorMessage } from '@/lib/api-error';
import type { ExportFormat } from '@/types/reports';

const reports = [
  { value: 'sales:summary', label: 'Sales summary' },
  { value: 'inventory:summary', label: 'Inventory summary' },
  { value: 'finance:summary', label: 'Finance summary' },
];

function Values({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value)).slice(0, 12);
  if (!entries.length) return <p className="py-8 text-center text-sm text-muted-foreground">The report returned no summary values for this period.</p>;
  return <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{entries.map(([key, value]) => <div key={key} className="rounded-lg border bg-background p-4"><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{key.replace(/_/g, ' ')}</dt><dd className="mt-2 break-words text-lg font-semibold">{String(value)}</dd></div>)}</dl>;
}

export default function ReportsDashboard() {
  const [selection, setSelection] = useState(reports[0].value);
  const [preset, setPreset] = useState('THIS_MONTH');
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [message, setMessage] = useState('');
  const [domain, report] = selection.split(':');
  const client=useQueryClient();const schedules=useQuery({queryKey:['report-schedules'],queryFn:reportsService.schedules});
  const run=useMutation({mutationFn:reportsService.runSchedule,onSuccess:(result)=>{setMessage(`Report ${result.report.status}; email ${result.email.status}.`);client.invalidateQueries({queryKey:['report-schedules']})},onError:(error)=>setMessage(getApiErrorMessage(error))});
  const query = useQuery({ queryKey: ['report', domain, report, preset], queryFn: () => reportsService.get(domain, report, { preset }) });
  const exportReport = async (format: ExportFormat) => { try { setMessage(''); setExporting(format); await reportsService.export(`${domain}_${report}`, format, { preset }); setMessage(`${format} export downloaded.`); } catch (error) { setMessage(getApiErrorMessage(error)); } finally { setExporting(null); } };
  return <div className="mx-auto max-w-[1400px] space-y-6">
    <header><p className="text-sm text-muted-foreground">Business intelligence</p><h2 className="mt-1 text-3xl font-semibold">Reports</h2><p className="mt-2 text-sm text-muted-foreground">Live server-calculated reports with secure exports.</p></header>
    <section className="flex flex-col gap-3 rounded-xl border bg-card p-4 sm:flex-row sm:items-end">
      <label className="flex-1 text-sm font-medium">Report<select value={selection} onChange={(event) => setSelection(event.target.value)} className="mt-2 h-11 w-full rounded-lg border bg-background px-3">{reports.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label className="flex-1 text-sm font-medium">Period<select value={preset} onChange={(event) => setPreset(event.target.value)} className="mt-2 h-11 w-full rounded-lg border bg-background px-3"><option value="TODAY">Today</option><option value="THIS_WEEK">This week</option><option value="THIS_MONTH">This month</option><option value="THIS_QUARTER">This quarter</option><option value="THIS_YEAR">This year</option></select></label>
      <button type="button" onClick={() => query.refetch()} disabled={query.isFetching} className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-semibold disabled:opacity-50"><RefreshCw className={`size-4 ${query.isFetching ? 'animate-spin' : ''}`} />Refresh</button>
    </section>
    <section className="rounded-xl border bg-card p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{reports.find((item) => item.value === selection)?.label}</h3><div className="flex flex-wrap gap-2">{(['PDF', 'XLSX', 'CSV'] as ExportFormat[]).map((format) => <button key={format} type="button" onClick={() => exportReport(format)} disabled={Boolean(exporting)} className="inline-flex h-10 items-center gap-2 rounded-lg border px-3 text-sm font-semibold disabled:cursor-wait disabled:opacity-50">{exporting === format ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}{format}</button>)}<button type="button" onClick={() => window.print()} className="inline-flex h-10 items-center gap-2 rounded-lg border px-3 text-sm font-semibold"><Printer className="size-4" />Print</button></div></div>
      {message && <p role="status" className="mb-4 rounded-lg bg-muted px-3 py-2 text-sm">{message}</p>}
      {query.isPending ? <div className="h-48 animate-pulse rounded-lg bg-muted" /> : query.isError ? <div role="alert" className="rounded-lg border border-destructive/20 p-4 text-sm text-destructive">{getApiErrorMessage(query.error)} <button type="button" onClick={() => query.refetch()} className="ml-2 underline">Retry</button></div> : <Values data={query.data} />}
    </section>
    <section className="rounded-xl border bg-card p-5"><div><h3 className="font-semibold">Weekly owner report automation</h3><p className="mt-1 text-sm text-muted-foreground">Generate the authoritative PDF and attempt delivery to each configured recipient. Report and email statuses are independent.</p></div>{schedules.isPending?<div className="mt-4 h-24 animate-pulse rounded-lg bg-muted"/>:schedules.data?.length?<div className="mt-4 space-y-3">{schedules.data.map(schedule=><article key={schedule.id} className="flex flex-col justify-between gap-3 rounded-lg border p-4 sm:flex-row sm:items-center"><div><p className="font-medium">{schedule.name}</p><p className="mt-1 text-xs text-muted-foreground">{schedule.frequency} · {schedule.timezone} · {schedule.recipient_emails_json.join(', ')||'No recipient configured'} · {schedule.is_active?'Enabled':'Disabled'}</p>{schedule.last_run_at&&<p className="mt-1 text-xs text-muted-foreground">Last run {new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(schedule.last_run_at))}</p>}</div><button onClick={()=>run.mutate(schedule.id)} disabled={run.isPending} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50">{run.isPending?<LoaderCircle className="size-4 animate-spin"/>:<Send className="size-4"/>}Generate & send now</button></article>)}</div>:<p className="mt-4 rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">No report schedule is configured. Create one through the report schedule API; automatic execution will be connected to the production scheduler during Phase 8.</p>}</section>
  </div>;
}
