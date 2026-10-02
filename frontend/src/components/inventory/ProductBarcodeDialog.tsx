import { useEffect, useState } from 'react';
import { Download, LoaderCircle, Printer, X } from 'lucide-react';
import { productsService, type BarcodeData } from '@/services/products.service';
import { getApiErrorMessage } from '@/lib/api-error';
import type { BackendProduct } from '@/types/products';
import { formatThermalLabelPrice, openThermalLabelPrintWindow } from '@/lib/barcode-label';

export function ProductBarcodeDialog({ productId, onClose }: { productId: string; onClose: () => void }) {
  const [product, setProduct] = useState<BackendProduct | null>(null);
  const [barcode, setBarcode] = useState<BarcodeData | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    void (async () => {
      try {
        const loaded = await productsService.get(productId);
        setProduct(loaded);
        if (!loaded.barcode) throw new Error('Barcode configuration error. Ask an administrator to run the barcode audit.');
        const existing = await productsService.getBarcode(productId);
        if (!existing.image_url) throw new Error('Barcode configuration error. The printable barcode image is unavailable.');
        setBarcode(existing);
      } catch (reason) {
        setError(getApiErrorMessage(reason));
      } finally {
        setBusy(false);
      }
    })();
  }, [productId]);

  const priceIsValid = Boolean(product && product.selling_price !== '' && Number.isFinite(Number(product.selling_price)) && Number(product.selling_price) >= 0);
  const download = () => {
    if (!barcode?.image_url) return;
    const link = document.createElement('a');
    link.href = barcode.image_url;
    link.download = `${product?.sku || 'ANICRAZE'}-barcode.svg`;
    link.click();
  };
  const print = () => {
    if (!product || !barcode?.image_url || !priceIsValid) {
      setError('Barcode configuration error. This product is not ready to print.');
      return;
    }
    try {
      openThermalLabelPrintWindow(Array.from({ length: quantity }, () => ({ productName: product.name, barcode: barcode.barcode, barcodeImageUrl: barcode.image_url!, sellingPrice: product.selling_price })), `${product.name} barcode labels`);
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    }
  };

  return <div className="fixed inset-0 z-[90] flex items-end justify-center bg-zinc-950/55 sm:items-center sm:p-5" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section role="dialog" aria-modal="true" className="w-full max-w-lg rounded-t-2xl bg-background shadow-2xl sm:rounded-2xl">
      <header className="flex items-center justify-between border-b p-5"><div><p className="text-xs font-semibold uppercase tracking-widest text-primary">Ready-to-print label</p><h2 className="mt-1 font-semibold">Barcode & label</h2></div><button onClick={onClose} className="grid size-9 place-items-center rounded-lg border"><X className="size-4"/></button></header>
      <div className="p-5">{error && <p className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}{busy ? <div className="grid min-h-56 place-items-center"><LoaderCircle className="animate-spin"/></div> : product && barcode?.image_url && priceIsValid && <div className="text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">50 × 25 mm thermal label preview</p>
        <div className="mx-auto mt-4 flex aspect-[2/1] w-full max-w-[400px] flex-col items-center overflow-hidden bg-white px-4 py-3 text-zinc-950 shadow-md"><p title={product.name} className={`h-[18px] w-full truncate pt-0.5 font-bold leading-4 ${product.name.length > 42 ? 'text-[10px]' : product.name.length > 28 ? 'text-[11px]' : 'text-xs'}`}>{product.name}</p><div className="mt-1 min-h-0 w-full flex-1 overflow-hidden"><img src={barcode.image_url} alt={`Barcode ${barcode.barcode}`} className="h-[144%] w-full object-fill"/></div><p className="font-mono text-[11px] font-semibold">{barcode.barcode}</p><p className="text-lg font-extrabold leading-tight">{formatThermalLabelPrice(product.selling_price)}</p></div>
        <p className="mt-3 text-xs text-muted-foreground">Print at 100% scale on a 50 × 25 mm label. Disable browser headers and footers.</p>
        <label className="mx-auto mt-4 block max-w-36 text-left text-xs font-semibold">Label quantity<input type="number" min="1" max="100" value={quantity} onChange={event => setQuantity(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} className="mt-1 h-11 w-full rounded-lg border px-3 text-center text-sm"/></label>
        <div className="mt-5 grid grid-cols-2 gap-2"><button onClick={download} className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border text-sm font-semibold"><Download className="size-4"/>Download SVG</button><button onClick={print} className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground"><Printer className="size-4"/>Print {quantity} {quantity === 1 ? 'Label' : 'Labels'}</button></div>
      </div>}</div>
    </section>
  </div>;
}
