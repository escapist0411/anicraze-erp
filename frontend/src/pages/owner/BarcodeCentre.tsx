import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Barcode, Printer, TriangleAlert } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { productsService } from '@/services/products.service';
import { inventoryService } from '@/services/inventory';
import { BulkBarcodePrintDialog } from '@/components/inventory/BulkBarcodePrintDialog';
import { ProductBarcodeDialog } from '@/components/inventory/ProductBarcodeDialog';
import type { BackendProduct } from '@/types/products';
import type { Page } from '@/types/api';
import { useAuth } from '@/hooks/useAuth';
import { formatThermalLabelPrice } from '@/lib/barcode-label';

const barcodePattern = /^[A-Za-z0-9_-]{4,64}$/;
const isReady = (product: BackendProduct) => Boolean(product.barcode && barcodePattern.test(product.barcode) && Number.isFinite(Number(product.selling_price)) && Number(product.selling_price) >= 0);

async function allProducts() {
  const first = await productsService.list({ page: 1, page_size: 100, status: 'ACTIVE' });
  if (Array.isArray(first)) return first as BackendProduct[];
  const page = first as Page<BackendProduct>;
  if (page.pages <= 1) return page.items;
  const rest = await Promise.all(Array.from({ length: page.pages - 1 }, (_, index) => productsService.list({ page: index + 2, page_size: 100, status: 'ACTIVE' })));
  return [page.items, ...rest.map(result => Array.isArray(result) ? result : result.items)].flat() as BackendProduct[];
}

export default function BarcodeCentre() {
  const { user } = useAuth();
  const base = `/${user?.role || 'owner'}`;
  const [params] = useSearchParams();
  const receiptId = params.get('receipt');
  const products = useQuery({ queryKey: ['products', 'barcodes'], queryFn: allProducts });
  const receipt = useQuery({ queryKey: ['stock-receipt', receiptId], queryFn: () => inventoryService.receipt(receiptId!), enabled: Boolean(receiptId) });
  const [single, setSingle] = useState<string | null>(null);
  const [bulk, setBulk] = useState(false);
  const [search, setSearch] = useState('');
  const receiptAutoOpened = useRef(false);

  useEffect(() => {
    if (receiptId && receipt.data && products.data && !receiptAutoOpened.current) {
      receiptAutoOpened.current = true;
      setBulk(true);
    }
  }, [products.data, receipt.data, receiptId]);

  const list = products.data || [];
  const visible = list.filter(product => `${product.name} ${product.sku} ${product.barcode || ''}`.toLowerCase().includes(search.toLowerCase()));
  const printProducts = list.map(product => ({ id: product.id, name: product.name, sku: product.sku, barcode: product.barcode, sellingPrice: product.selling_price }));
  const defaults = Object.fromEntries((receipt.data?.items || []).map(item => [item.product_id, item.expected_quantity]));

  return <div className="mx-auto max-w-[1500px] space-y-6">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-primary">Ready-to-print product labels</p><h1 className="mt-1 text-3xl font-semibold">Barcode Centre</h1><p className="mt-2 text-sm text-muted-foreground">Select products, choose label quantities, and print approved 50 × 25 mm thermal labels.</p></div>
      <button onClick={() => setBulk(true)} disabled={!list.some(isReady)} className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"><Printer className="size-4"/>Print Product Barcodes</button>
    </header>
    {receipt.data && <section className="rounded-xl border border-primary/30 bg-primary/5 p-4"><p className="font-semibold">Receiving Batch {receipt.data.reference_number}</p><p className="mt-1 text-sm text-muted-foreground">{receipt.data.total_products} products · {receipt.data.total_expected} labels selected by default.</p><Link to={`${base}/godown-intake?receipt=${receipt.data.id}`} className="mt-3 inline-flex h-10 items-center gap-2 rounded-lg border bg-background px-4 text-sm font-semibold">Start Godown Scanning<ArrowRight className="size-4"/></Link></section>}
    <label className="flex h-12 items-center rounded-xl border bg-card px-3"><Barcode className="size-5"/><input value={search} onChange={event => setSearch(event.target.value)} className="min-w-0 flex-1 bg-transparent px-3 outline-none" placeholder="Search product, SKU, or barcode"/></label>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{visible.map(product => {
      const ready = isReady(product);
      return <article key={product.id} className={`rounded-xl border bg-card p-4 ${ready ? '' : 'border-destructive/30'}`}>
        <div className="flex items-start justify-between gap-3"><div className="min-w-0"><strong className="block truncate">{product.name}</strong><span className="mt-1 block truncate font-mono text-xs text-muted-foreground">{product.barcode || 'Barcode configuration error'}</span><span className="mt-2 block font-semibold">{Number.isFinite(Number(product.selling_price)) && Number(product.selling_price) >= 0 ? formatThermalLabelPrice(product.selling_price) : 'Price configuration error'}</span></div>{ready ? <Barcode className="size-5 shrink-0 text-primary"/> : <TriangleAlert className="size-5 shrink-0 text-destructive"/>}</div>
        <button disabled={!ready} onClick={() => ready && setSingle(product.id)} className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"><Printer className="size-4"/>{ready ? 'Print Labels' : 'Barcode configuration error'}</button>
      </article>;
    })}</div>
    {single && <ProductBarcodeDialog productId={single} onClose={() => setSingle(null)}/>}
    {bulk && <BulkBarcodePrintDialog products={printProducts} initialSelection={defaults} onClose={() => setBulk(false)}/>}
  </div>;
}
