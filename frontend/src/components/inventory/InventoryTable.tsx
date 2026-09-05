import { useMemo, useState } from 'react';
import {
  ArrowDownUp,
  ChevronLeft,
  ChevronRight,
  Eye,
  MoreHorizontal,
  Package,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import type { Product } from './data';
import { cn } from '@/lib/utils';
import { MobileDataCard } from '@/components/responsive/MobileDataCard';

const headers = [
  'Product',
  'SKU',
  'Barcode',
  'Category',
  'Brand',
  'Store',
  'Purchase',
  'Selling',
  'Current',
  'Minimum',
  'Status',
  'Last updated',
  '',
];

export function InventoryTable({ onOpen, products=[], total=products.length }: { onOpen: (product: Product) => void; products?: Product[]; total?: number }) {
  const [query, setQuery] = useState('');
  const [sortAsc, setSortAsc] = useState(true);
  const [status, setStatus] = useState('All statuses');
  const rows = useMemo(
    () => products
      .filter((product) => (
        (status === 'All statuses' || product.status === status)
        && `${product.name} ${product.sku} ${product.category}`.toLowerCase().includes(query.toLowerCase())
      ))
      .sort((a, b) => (sortAsc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name))),
    [query, sortAsc, status],
  );

  return (
    <section className="min-w-0 max-w-full overflow-hidden rounded-xl border bg-card shadow-sm">
      <div className="flex min-w-0 flex-col gap-4 p-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <h3 className="font-semibold">Product inventory</h3>
          <p className="mt-1 text-xs text-muted-foreground">{total} live inventory records</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-2">
          <label className="flex h-9 w-full min-w-0 items-center rounded-lg border bg-background px-3 sm:w-auto sm:min-w-52">
            <Search className="size-4 shrink-0 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search SKU, name…"
              className="min-w-0 flex-1 bg-transparent px-2 text-xs outline-none"
            />
          </label>
          <select value={status} onChange={(event) => setStatus(event.target.value)} className="h-9 rounded-lg border bg-background px-2 text-xs outline-none">
            <option>All statuses</option>
            <option>Active</option>
            <option>Low stock</option>
            <option>Out of stock</option>
          </select>
          <button onClick={() => setSortAsc((value) => !value)} className="inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-semibold hover:bg-muted">
            <ArrowDownUp className="size-3.5" />
            Sort
          </button>
          <button className="grid size-9 place-items-center rounded-lg border hover:bg-muted" aria-label="Filter inventory">
            <SlidersHorizontal className="size-4" />
          </button>
        </div>
      </div>

      <div className="grid gap-3 px-4 pb-4 md:hidden">
        {rows.map((product) => <MobileDataCard key={product.id} title={product.name} subtitle={`${product.sku} · ${product.barcode}`} status={<span className={cn('shrink-0 rounded-full px-2 py-1 text-xs font-semibold',product.status==='Active'?'bg-emerald-500/10 text-emerald-700':product.status==='Low stock'?'bg-amber-500/10 text-amber-700':'bg-rose-500/10 text-rose-700')}>{product.status}</span>} actions={<button onClick={()=>onOpen(product)} className="inline-flex min-h-11 items-center gap-2 rounded-lg border px-3 text-sm font-semibold"><Eye className="size-4"/>View details</button>}><div><dt className="text-xs text-muted-foreground">Location</dt><dd className="mt-1 truncate font-medium">{product.store}</dd></div><div><dt className="text-xs text-muted-foreground">Available</dt><dd className="mt-1 font-semibold">{product.stock}</dd></div><div><dt className="text-xs text-muted-foreground">Selling price</dt><dd className="mt-1 font-medium">₹{product.sellingPrice.toLocaleString('en-IN')}</dd></div><div><dt className="text-xs text-muted-foreground">Minimum</dt><dd className="mt-1 font-medium">{product.minimumStock}</dd></div></MobileDataCard>)}
        {!rows.length&&<p className="rounded-xl border p-6 text-center text-sm text-muted-foreground">No inventory matches your filters.</p>}
      </div>
      <div className="hidden max-w-full overflow-x-auto md:block">
        <table className="w-full min-w-[1450px] text-left text-sm">
          <thead className="sticky top-0 z-10 border-y bg-muted/60 text-[10px] font-bold tracking-[.08em] text-muted-foreground uppercase">
            <tr>
              {headers.map((header) => (
                <th key={header} className="whitespace-nowrap px-3 py-3 first:px-5">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((product) => (
              <tr key={product.id} className="transition hover:bg-muted/35">
                <td className="px-5 py-3">
                  <button onClick={() => onOpen(product)} className="flex items-center gap-3 text-left">
                    <span className={`grid size-9 place-items-center rounded-lg bg-gradient-to-br ${product.hue} text-white shadow-sm`}>
                      <Package className="size-4" />
                    </span>
                    <span className="font-medium hover:text-primary">{product.name}</span>
                  </button>
                </td>
                <td className="px-3 py-3 font-mono text-xs">{product.sku}</td>
                <td className="px-3 py-3 font-mono text-xs text-muted-foreground">{product.barcode}</td>
                <td className="px-3 py-3 text-xs text-muted-foreground">{product.category}</td>
                <td className="px-3 py-3 text-xs">{product.brand}</td>
                <td className="px-3 py-3 text-xs">{product.store}</td>
                <td className="px-3 py-3 text-xs">₹{product.purchasePrice.toLocaleString('en-IN')}</td>
                <td className="px-3 py-3 text-xs font-semibold">₹{product.sellingPrice.toLocaleString('en-IN')}</td>
                <td className="px-3 py-3 text-center font-semibold">{product.stock}</td>
                <td className="px-3 py-3 text-center text-xs">{product.minimumStock}</td>
                <td className="px-3 py-3">
                  <span className={cn(
                    'rounded-full px-2 py-1 text-[10px] font-semibold',
                    product.status === 'Active'
                      ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                      : product.status === 'Low stock'
                        ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
                        : 'bg-rose-500/10 text-rose-700 dark:text-rose-400',
                  )}
                  >
                    {product.status}
                  </span>
                </td>
                <td className="px-3 py-3 text-xs text-muted-foreground">{product.updated}</td>
                <td className="px-3 py-3">
                  <div className="flex">
                    <button onClick={() => onOpen(product)} className="grid size-7 place-items-center rounded-md hover:bg-muted" aria-label={`View ${product.name}`}>
                      <Eye className="size-3.5" />
                    </button>
                    <button className="grid size-7 place-items-center rounded-md hover:bg-muted" aria-label={`More options for ${product.name}`}>
                      <MoreHorizontal className="size-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 border-t px-4 py-3 sm:px-5">
        <p className="min-w-0 truncate text-xs text-muted-foreground">Showing {rows.length} of {total} products</p>
        <div className="flex shrink-0 gap-1">
          <button className="grid size-8 place-items-center rounded-md border text-muted-foreground" aria-label="Previous page"><ChevronLeft className="size-4" /></button>
          <button className="grid size-8 place-items-center rounded-md bg-primary text-xs font-semibold text-primary-foreground">1</button>
          <button className="grid size-8 place-items-center rounded-md border text-xs">2</button>
          <button className="grid size-8 place-items-center rounded-md border text-xs">3</button>
          <button className="grid size-8 place-items-center rounded-md border text-muted-foreground" aria-label="Next page"><ChevronRight className="size-4" /></button>
        </div>
      </div>
    </section>
  );
}
