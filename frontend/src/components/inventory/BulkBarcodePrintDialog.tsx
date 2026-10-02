import { useMemo, useState } from 'react';
import { Barcode, CheckSquare, LoaderCircle, Printer, Search, Square, TriangleAlert, X } from 'lucide-react';
import { productsService, type BarcodeData } from '@/services/products.service';
import type { BackendProduct } from '@/types/products';
import { getApiErrorMessage } from '@/lib/api-error';
import { formatThermalLabelPrice, openThermalLabelPrintWindow } from '@/lib/barcode-label';

interface BarcodeProduct { id: string; name: string; sku: string; barcode: string | null; sellingPrice: string | number }
interface Prepared { product: BackendProduct; barcode: BarcodeData; quantity: number }
const barcodePattern = /^[A-Za-z0-9_-]{4,64}$/;
const isReady = (product: BarcodeProduct) => Boolean(product.barcode && barcodePattern.test(product.barcode) && product.sellingPrice !== '' && Number.isFinite(Number(product.sellingPrice)) && Number(product.sellingPrice) >= 0);

export function BulkBarcodePrintDialog({ products, onClose, initialSelection = {} }: { products: BarcodeProduct[]; onClose: () => void; initialSelection?: Record<string, number> }) {
  const readyIds = useMemo(() => new Set(products.filter(isReady).map(product => product.id)), [products]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Record<string, number>>(() => Object.fromEntries(Object.entries(initialSelection).filter(([id]) => readyIds.has(id))));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const visible = useMemo(() => products.filter(product => `${product.name} ${product.sku} ${product.barcode || ''}`.toLowerCase().includes(search.toLowerCase())), [products, search]);
  const count = Object.keys(selected).length;
  const total = Object.values(selected).reduce((sum, value) => sum + value, 0);

  const toggle = (id: string) => {
    if (!readyIds.has(id)) return;
    setSelected(current => current[id] ? Object.fromEntries(Object.entries(current).filter(([key]) => key !== id)) : { ...current, [id]: 1 });
  };
  const selectVisible = () => setSelected(current => {
    const next = { ...current };
    for (const product of visible) if (isReady(product)) next[product.id] = next[product.id] || 1;
    return next;
  });
  const prepare = async () => {
    const result: Prepared[] = [];
    for (const [id, quantity] of Object.entries(selected)) {
      const product = await productsService.get(id);
      if (!product.barcode || !barcodePattern.test(product.barcode) || product.selling_price === '' || !Number.isFinite(Number(product.selling_price)) || Number(product.selling_price) < 0) {
        throw new Error(`Barcode configuration error for ${product.name}.`);
      }
      const barcode = await productsService.getBarcode(id);
      if (!barcode.image_url) throw new Error(`Barcode configuration error for ${product.name}: printable image unavailable.`);
      result.push({ product, barcode, quantity });
    }
    return result;
  };
  const print = async () => {
    if (count === readyIds.size && !window.confirm(`Print labels for all ${readyIds.size} ready products?`)) return;
    setBusy(true);
    setError('');
    try {
      const labels = await prepare();
      openThermalLabelPrintWindow(labels.flatMap(({ product, barcode, quantity }) => Array.from({ length: quantity }, () => ({ productName: product.name, barcode: barcode.barcode, barcodeImageUrl: barcode.image_url!, sellingPrice: product.selling_price }))), 'ANICRAZE thermal barcode labels');
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  return <div className="fixed inset-0 z-[95] flex items-end justify-center bg-zinc-950/60 sm:items-center sm:p-5" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section role="dialog" aria-modal="true" className="flex max-h-[94dvh] w-full max-w-4xl flex-col rounded-t-2xl bg-background shadow-2xl sm:rounded-2xl">
      <header className="flex items-center justify-between border-b p-5"><div><p className="text-xs font-semibold uppercase tracking-widest text-primary">Barcode Centre</p><h2 className="mt-1 text-lg font-semibold">Print multiple barcode labels</h2><p className="mt-1 text-xs text-muted-foreground">One 50 × 25 mm thermal label per selected copy.</p></div><button onClick={onClose} className="grid size-10 place-items-center rounded-lg border"><X className="size-4"/></button></header>
      <div className="flex min-h-0 flex-1 flex-col p-4 sm:p-5">{error && <p role="alert" className="mb-3 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}<div className="mb-3 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">SEZNIK JOSH: choose 50 × 25 mm paper, 100% scale, zero margins, and disable headers/footers.</div><div className="flex flex-col gap-2 sm:flex-row"><label className="flex h-11 flex-1 items-center rounded-lg border px-3"><Search className="size-4 text-muted-foreground"/><input autoFocus value={search} onChange={event => setSearch(event.target.value)} className="min-w-0 flex-1 bg-transparent px-2 text-sm outline-none" placeholder="Search product, SKU or barcode"/></label><button onClick={selectVisible} className="h-11 rounded-lg border px-4 text-sm font-semibold">Select ready</button><button onClick={() => setSelected({})} className="h-11 rounded-lg border px-4 text-sm font-semibold">Clear</button></div>
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto rounded-xl border"><div className="grid grid-cols-[40px_1fr_100px] bg-muted/40 px-3 py-2 text-xs font-semibold text-muted-foreground"><span/><span>Product</span><span className="text-center">Labels</span></div><div className="divide-y">{visible.map(product => { const quantity = selected[product.id]; const ready = isReady(product); return <div key={product.id} className={`grid grid-cols-[40px_1fr_100px] items-center px-3 py-3 ${quantity ? 'bg-primary/[.03]' : ''}`}><button disabled={!ready} onClick={() => toggle(product.id)} className="grid size-9 place-items-center disabled:opacity-40" aria-label={`Select ${product.name}`}>{!ready ? <TriangleAlert className="size-5 text-destructive"/> : quantity ? <CheckSquare className="size-5 text-primary"/> : <Square className="size-5 text-muted-foreground"/>}</button><button disabled={!ready} onClick={() => toggle(product.id)} className="min-w-0 text-left disabled:cursor-not-allowed"><span className="block truncate text-sm font-semibold">{product.name}</span><span className={`block truncate text-xs ${ready ? 'text-muted-foreground' : 'text-destructive'}`}>{ready ? `${product.barcode} · ${formatThermalLabelPrice(product.sellingPrice)}` : 'Barcode configuration error'}</span></button><input disabled={!quantity} type="number" min="1" max="100" value={quantity || 1} onChange={event => setSelected(current => ({ ...current, [product.id]: Math.max(1, Math.min(100, Number(event.target.value) || 1)) }))} className="h-10 rounded-lg border px-2 text-center disabled:opacity-40" aria-label={`Label count for ${product.name}`}/></div>; })}{!visible.length && <p className="p-8 text-center text-sm text-muted-foreground">No products match the search.</p>}</div></div>
      </div>
      <footer className="flex flex-col justify-between gap-3 border-t bg-muted/20 p-4 sm:flex-row sm:items-center sm:px-5"><div className="flex items-center gap-2 text-sm"><Barcode className="size-4 text-primary"/><strong>{count}</strong> product types · <strong>{total}</strong> labels</div><div className="flex gap-2"><button onClick={onClose} className="h-11 rounded-lg border px-4 text-sm font-semibold">Cancel</button><button onClick={print} disabled={busy || !count} className="inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-50 sm:flex-none">{busy ? <LoaderCircle className="size-4 animate-spin"/> : <Printer className="size-4"/>}{busy ? 'Preparing labels…' : `Print ${total} labels`}</button></div></footer>
    </section>
  </div>;
}
