import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { procurementServices } from '@/services/domain-services';
import { queryKeys } from '@/lib/query-keys';
import { getApiErrorMessage } from '@/lib/api-error';
import { formatCurrency } from '@/lib/format';
import { useAuth } from '@/hooks/useAuth';

type Supplier = { id: string; supplier_code: string; display_name: string; company_name: string; email: string | null; phone: string | null; outstanding_balance: string; status: string };

export default function Suppliers() {
  const { user } = useAuth();
  const owner = user?.role === 'owner';
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const query = useQuery({
    queryKey: queryKeys.procurement('suppliers'),
    queryFn: () => procurementServices.suppliers.list() as Promise<Supplier[]>,
    enabled: owner,
  });
  const create = useMutation({
    mutationFn: () => procurementServices.suppliers.create({
      display_name: displayName.trim(),
      company_name: companyName.trim() || displayName.trim(),
      email: email.trim() || null,
      phone: phone.trim() || null,
    }),
    onSuccess: async () => {
      setOpen(false);
      setDisplayName('');
      setCompanyName('');
      setEmail('');
      setPhone('');
      await client.invalidateQueries({ queryKey: queryKeys.procurement('suppliers') });
    },
  });

  if (!owner) {
    return <div className="rounded-xl border bg-card p-6 text-sm">Supplier administration and purchase balances are Owner-only.</div>;
  }

  return <div className="mx-auto max-w-[1680px] space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="text-sm text-muted-foreground">Procurement</p><h2 className="mt-1 text-2xl font-semibold">Suppliers</h2></div>
      <button onClick={() => setOpen(true)} className="h-11 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground">Add supplier</button>
    </div>
    {open && <form onSubmit={event => { event.preventDefault(); if (!create.isPending) create.mutate(); }} className="space-y-4 rounded-xl border bg-card p-5">
      <h3 className="font-semibold">New supplier</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-semibold">Display name<input required minLength={2} maxLength={180} value={displayName} onChange={event => setDisplayName(event.target.value)} className="mt-1 h-11 w-full rounded-lg border px-3"/></label>
        <label className="text-xs font-semibold">Company name<input maxLength={180} value={companyName} onChange={event => setCompanyName(event.target.value)} className="mt-1 h-11 w-full rounded-lg border px-3"/></label>
        <label className="text-xs font-semibold">Email (optional)<input type="email" value={email} onChange={event => setEmail(event.target.value)} className="mt-1 h-11 w-full rounded-lg border px-3"/></label>
        <label className="text-xs font-semibold">Phone (optional)<input value={phone} onChange={event => setPhone(event.target.value)} className="mt-1 h-11 w-full rounded-lg border px-3"/></label>
      </div>
      {create.isError && <p role="alert" className="text-sm text-destructive">{getApiErrorMessage(create.error)}</p>}
      <div className="flex gap-2"><button disabled={create.isPending || displayName.trim().length < 2} className="h-11 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50">Save supplier</button><button type="button" onClick={() => setOpen(false)} className="h-11 rounded-lg border px-4 text-sm">Cancel</button></div>
    </form>}
    {query.isPending ? <div className="h-64 animate-pulse rounded-xl bg-muted"/> : query.isError ? <button onClick={() => query.refetch()} className="rounded-lg border p-4">Unable to load suppliers. Retry</button> : <div className="overflow-x-auto rounded-xl border bg-card"><table className="w-full min-w-[720px] text-left text-sm"><thead className="border-b bg-muted/40"><tr><th className="p-4">Supplier</th><th className="p-4">Contact</th><th className="p-4">Status</th><th className="p-4 text-right">Outstanding</th></tr></thead><tbody className="divide-y">{query.data.map(item => <tr key={item.id}><td className="p-4"><p className="font-medium">{item.display_name}</p><p className="text-xs text-muted-foreground">{item.supplier_code} · {item.company_name}</p></td><td className="p-4 text-xs">{item.email || item.phone || '—'}</td><td className="p-4">{item.status}</td><td className="p-4 text-right">{formatCurrency(item.outstanding_balance)}</td></tr>)}</tbody></table>{!query.data.length && <p className="p-8 text-center text-muted-foreground">No suppliers found. Add one before tracking a purchase payable.</p>}</div>}
  </div>;
}
