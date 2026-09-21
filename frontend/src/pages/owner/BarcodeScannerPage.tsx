import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, CircleHelp, PackageCheck, ScanLine, Search, TriangleAlert, XCircle } from 'lucide-react';
import { BarcodeScanner } from '@/components/responsive/BarcodeScanner';
import { getApiErrorMessage } from '@/lib/api-error';
import { inventoryService } from '@/services/inventory';
import { productsService } from '@/services/products.service';
import type { BackendProduct } from '@/types/products';
import type { InventoryRecord, StockReceipt, StockTransfer } from '@/types/inventory';

type Mode = 'test' | 'intake' | 'lookup' | 'pick' | 'receive';
type Feedback = { kind: 'success' | 'warning' | 'error'; title: string; code: string; detail: string };
type LogRow = { id: number; time: string; product: string; result: string; ok: boolean };

export default function BarcodeScannerPage() {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const queue = useRef(Promise.resolve());
  const [ready, setReady] = useState(false);
  const [code, setCode] = useState('');
  const [mode, setMode] = useState<Mode>('test');
  const [receiptId, setReceiptId] = useState('');
  const [transferId, setTransferId] = useState('');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [lookup, setLookup] = useState<InventoryRecord[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [log, setLog] = useState<LogRow[]>([]);
  const [camera, setCamera] = useState(false);
  const [help, setHelp] = useState(false);

  const receipts = useQuery({ queryKey: ['stock-receipts'], queryFn: inventoryService.receipts });
  const receipt = useQuery({ queryKey: ['stock-receipt', receiptId], queryFn: () => inventoryService.receipt(receiptId), enabled: Boolean(receiptId) });
  const transfers = useQuery({ queryKey: ['stock-transfers'], queryFn: inventoryService.transfers });
  const transfer = useQuery({ queryKey: ['stock-transfer', transferId], queryFn: () => inventoryService.transferDetail(transferId), enabled: Boolean(transferId) });
  const pendingReceipts = (receipts.data || []).filter((item) => !['COMPLETED', 'CANCELLED'].includes(item.status));
  const eligibleTransfers = (transfers.data || []).filter((item) => mode === 'pick' ? ['APPROVED', 'PICKING'].includes(item.status) : ['DISPATCHED', 'RECEIVING'].includes(item.status));

  useEffect(() => { setCounts({}); setFeedback(null); }, [mode, transferId]);
  useEffect(() => { if (ready) requestAnimationFrame(() => input.current?.focus()); }, [ready, feedback]);

  const addLog = (product: string, result: string, ok: boolean) => setLog((rows) => [{ id: Date.now() + Math.random(), time: new Date().toLocaleTimeString('en-IN'), product, result, ok }, ...rows].slice(0, 50));
  const productFor = async (raw: string) => {
    try { return await productsService.lookupBarcode(raw); }
    catch { try { return await productsService.lookupSku(raw); } catch { return null; } }
  };
  const showUnknown = (raw: string) => {
    setFeedback({ kind: 'warning', title: 'BARCODE RECEIVED', code: raw, detail: 'Scanner: WORKING · Product: NOT FOUND' });
    addLog(`Unknown ${raw}`, 'Not found', false);
  };

  const process = async (raw: string) => {
    const value = raw.trim();
    if (!value) return;
    setCode('');
    if (mode === 'intake') {
      if (!receiptId) return setFeedback({ kind: 'error', title: 'SELECT A RECEIPT', code: value, detail: 'Choose a pending receipt before scanning.' });
      try {
        const before = receipt.data;
        const updated = await inventoryService.scanReceipt(receiptId, value);
        qc.setQueryData(['stock-receipt', receiptId], updated);
        const item = updated.items.find((x) => x.barcode === value || x.sku === value);
        const previous = before?.items.find((x) => x.id === item?.id)?.scanned_quantity ?? 0;
        const title = item ? item.product_name : value;
        setFeedback({ kind: 'success', title: 'SCANNED', code: value, detail: item ? `${item.scanned_quantity} / ${item.expected_quantity}` : `${updated.total_scanned} / ${updated.total_expected}` });
        addLog(title, item ? `✓ ${previous + 1}/${item.expected_quantity}` : '✓', true);
      } catch (error) {
        const message = getApiErrorMessage(error);
        setFeedback({ kind: message.toLowerCase().includes('expected quantity') ? 'warning' : 'error', title: message.toLowerCase().includes('expected quantity') ? 'EXPECTED QUANTITY REACHED' : 'SCAN REJECTED', code: value, detail: message });
        addLog(value, message, false);
      }
      return;
    }

    const product = await productFor(value);
    if (!product) return showUnknown(value);
    if (mode === 'test') {
      setFeedback({ kind: 'success', title: 'SCANNED', code: value, detail: `${product.name} · Scanner input: WORKING` });
      addLog(product.name, '✓ Working', true);
      return;
    }
    if (mode === 'lookup') {
      const result = await inventoryService.list({ search: value, page_size: 100 });
      const rows = Array.isArray(result) ? result : result.items;
      setLookup(rows.filter((row) => row.product_id === product.id));
      setFeedback({ kind: 'success', title: 'STOCK FOUND', code: value, detail: `${product.name} · ₹${Number(product.selling_price).toLocaleString('en-IN')}` });
      addLog(product.name, '✓ Lookup', true);
      return;
    }
    const selected = transfer.data;
    if (!selected) return setFeedback({ kind: 'error', title: 'SELECT A TRANSFER', code: value, detail: 'Choose an eligible transfer before scanning.' });
    const item = selected.items.find((row) => row.product_id === product.id && (!row.variant_id || row.barcode === value || row.sku === value));
    if (!item) {
      setFeedback({ kind: 'error', title: 'PRODUCT NOT IN TRANSFER', code: value, detail: product.name });
      addLog(product.name, 'Not expected', false);
      return;
    }
    const current = counts[item.id] ?? (mode === 'pick' ? item.picked_quantity : item.received_quantity);
    if (current >= item.quantity) {
      setFeedback({ kind: 'warning', title: 'EXPECTED QUANTITY REACHED', code: value, detail: `${product.name} · ${current} / ${item.quantity}` });
      addLog(product.name, `Limit ${current}/${item.quantity}`, false);
      return;
    }
    const next = current + 1;
    setCounts((old) => ({ ...old, [item.id]: next }));
    setFeedback({ kind: 'success', title: 'SCANNED', code: value, detail: `${product.name} · ${next} / ${item.quantity}` });
    addLog(product.name, `✓ ${next}/${item.quantity}`, true);
  };

  const enqueue = (value: string) => {
    queue.current = queue.current.then(() => process(value)).catch((error) => setFeedback({ kind: 'error', title: 'SCAN ERROR', code: value, detail: getApiErrorMessage(error) }));
  };
  const submit = () => { enqueue(code); setCode(''); };
  const complete = useMemo(() => Boolean(transfer.data?.items.length) && transfer.data!.items.every((item) => (counts[item.id] ?? (mode === 'pick' ? item.picked_quantity : item.received_quantity)) === item.quantity), [counts, mode, transfer.data]);
  const confirmTransfer = useMutation({
    mutationFn: async () => {
      const selected = transfer.data!;
      if (mode === 'pick') return inventoryService.pickTransfer(selected.id, selected.items.map((item) => ({ item_id: item.id, picked_quantity: counts[item.id] ?? item.picked_quantity })));
      return inventoryService.receiveTransfer(selected.id, selected.items.map((item) => ({ item_id: item.id, received_quantity: counts[item.id] ?? item.received_quantity, damaged_quantity: 0, excess_quantity: 0 })));
    },
    onSuccess: (data: StockTransfer) => { qc.setQueryData(['stock-transfer', transferId], data); qc.invalidateQueries({ queryKey: ['stock-transfers'] }); setFeedback({ kind: 'success', title: mode === 'pick' ? 'PICKING COMPLETE' : 'RECEIPT CONFIRMED', code: data.reference_number, detail: 'Existing transfer workflow updated successfully.' }); },
  });
  const finalize = useMutation({ mutationFn: () => inventoryService.finalizeReceipt(receiptId), onSuccess: (data: StockReceipt) => { qc.setQueryData(['stock-receipt', receiptId], data); qc.invalidateQueries({ queryKey: ['stock-receipts'] }); qc.invalidateQueries({ queryKey: ['inventory'] }); setFeedback({ kind: 'success', title: 'STOCK ENTRY CONFIRMED', code: data.reference_number, detail: 'Central Warehouse inventory and ledger were updated.' }); } });

  return <div className="mx-auto max-w-6xl space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-primary">Physical scanning workspace</p><h1 className="mt-1 text-3xl font-semibold">Barcode Scanner</h1><p className="mt-2 text-sm text-muted-foreground">Connect the wireless scanner, click Start Scanner and scan a product barcode.</p></div><button onClick={() => setHelp(true)} className="inline-flex h-11 items-center gap-2 rounded-xl border px-4 font-semibold"><CircleHelp className="size-4"/>Scanner Setup</button></header>
    <section className="grid gap-3 sm:grid-cols-5">{([['test','Test Scanner'],['intake','Godown Intake'],['lookup','Stock Lookup'],['pick','Transfer Picking'],['receive','Shop Receiving']] as [Mode,string][]).map(([value,label])=><button key={value} onClick={()=>setMode(value)} className={`min-h-12 rounded-xl border px-3 text-sm font-semibold ${mode===value?'border-primary bg-primary text-primary-foreground':''}`}>{label}</button>)}</section>
    {mode==='intake'&&<select value={receiptId} onChange={(e)=>setReceiptId(e.target.value)} className="h-12 w-full rounded-xl border bg-card px-3"><option value="">Select pending receipt</option>{pendingReceipts.map((item)=><option key={item.id} value={item.id}>{item.reference_number} · {item.total_scanned}/{item.total_expected}</option>)}</select>}
    {(mode==='pick'||mode==='receive')&&<select value={transferId} onChange={(e)=>setTransferId(e.target.value)} className="h-12 w-full rounded-xl border bg-card px-3"><option value="">Select eligible transfer</option>{eligibleTransfers.map((item)=><option key={item.id} value={item.id}>{item.reference_number} · {item.status}</option>)}</select>}
    <section className="rounded-2xl border bg-card p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs text-muted-foreground">Scanner Status</p><p className={`mt-1 font-semibold ${ready?'text-emerald-600':'text-muted-foreground'}`}>● {ready?'READY FOR INPUT':'NOT STARTED'}</p></div><button onClick={()=>{setReady(true);requestAnimationFrame(()=>input.current?.focus())}} className="h-12 rounded-xl bg-primary px-6 font-semibold text-primary-foreground">Start Scanner</button></div>
      <label className="mt-5 flex h-14 items-center rounded-xl border px-3"><ScanLine className="size-5 text-primary"/><input ref={input} value={code} onChange={(e)=>setCode(e.target.value)} onKeyDown={(e)=>{if(e.key==='Enter'){e.preventDefault();submit()}}} disabled={!ready} className="min-w-0 flex-1 bg-transparent px-3 text-lg outline-none disabled:opacity-50" placeholder={ready?'Scan barcode here...':'Click Start Scanner first'}/><button onClick={submit} disabled={!ready} className="h-10 rounded-lg border px-4 text-sm font-semibold">Submit</button></label>
      <button onClick={()=>setCamera((value)=>!value)} className="mt-3 h-11 w-full rounded-xl border font-semibold">{camera?'Close Camera':'Use Camera'}</button>{camera&&<div className="mt-3"><BarcodeScanner onScan={enqueue}/></div>}
    </section>
    {feedback&&<section role="status" className={`rounded-2xl border p-5 ${feedback.kind==='success'?'border-emerald-500/30 bg-emerald-500/5':feedback.kind==='warning'?'border-amber-500/30 bg-amber-500/5':'border-destructive/30 bg-destructive/5'}`}><div className="flex gap-3">{feedback.kind==='success'?<CheckCircle2 className="text-emerald-600"/>:feedback.kind==='warning'?<TriangleAlert className="text-amber-600"/>:<XCircle className="text-destructive"/>}<div><h2 className="font-bold">{feedback.title}</h2><p className="font-mono text-sm">{feedback.code}</p><p className="mt-1 text-sm">{feedback.detail}</p></div></div></section>}
    {receipt.data&&mode==='intake'&&<section className="rounded-2xl border bg-card p-5"><h2 className="font-semibold">{receipt.data.reference_number}</h2><p className="text-sm">Expected {receipt.data.total_expected} · Scanned {receipt.data.total_scanned} · Remaining {receipt.data.total_expected-receipt.data.total_scanned}</p><div className="mt-3 divide-y">{receipt.data.items.map((item)=><div key={item.id} className="flex justify-between py-3"><span>{item.product_name}<small className="block text-muted-foreground">{item.sku}</small></span><b>{item.scanned_quantity} / {item.expected_quantity}</b></div>)}</div><button disabled={receipt.data.total_expected!==receipt.data.total_scanned||finalize.isPending} onClick={()=>window.confirm('Confirm stock entry into Central Warehouse?')&&finalize.mutate()} className="mt-3 inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary font-semibold text-primary-foreground disabled:opacity-40"><PackageCheck/>Confirm Stock Entry</button></section>}
    {lookup.length>0&&mode==='lookup'&&<section className="divide-y rounded-2xl border bg-card">{lookup.map((row)=><div key={row.id} className="flex justify-between gap-4 p-4"><div><b>{row.product_name}</b><p className="text-xs text-muted-foreground">{row.sku} · {row.barcode}</p></div><div className="text-right"><b>{row.available_quantity}</b><p className="text-xs text-muted-foreground">{row.warehouse?.name||row.store?.name}</p></div></div>)}</section>}
    {transfer.data&&(mode==='pick'||mode==='receive')&&<section className="rounded-2xl border bg-card p-5"><h2 className="font-semibold">{transfer.data.reference_number}</h2><div className="mt-3 divide-y">{transfer.data.items.map((item)=><div key={item.id} className="flex justify-between py-3"><span>{item.product_name}<small className="block text-muted-foreground">{item.sku}</small></span><b>{counts[item.id]??(mode==='pick'?item.picked_quantity:item.received_quantity)} / {item.quantity}</b></div>)}</div><button disabled={!complete||confirmTransfer.isPending} onClick={()=>window.confirm(mode==='pick'?'Confirm picked quantities?':'Confirm received quantities?')&&confirmTransfer.mutate()} className="mt-3 h-12 w-full rounded-xl bg-primary font-semibold text-primary-foreground disabled:opacity-40">{mode==='pick'?'Confirm Picking':'Confirm Receipt'}</button></section>}
    <section className="rounded-2xl border bg-card"><h2 className="border-b p-4 font-semibold">Current Session Activity</h2><div className="max-h-72 overflow-auto divide-y">{log.map((row)=><div key={row.id} className="grid grid-cols-[90px_1fr_auto] gap-3 p-3 text-sm"><span className="text-muted-foreground">{row.time}</span><span>{row.product}</span><b className={row.ok?'text-emerald-600':'text-destructive'}>{row.result}</b></div>)}{!log.length&&<p className="p-8 text-center text-sm text-muted-foreground">No scans in this session.</p>}</div></section>
    {help&&<><button aria-label="Close setup" onClick={()=>setHelp(false)} className="fixed inset-0 z-40 bg-black/50"/><section className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,560px)] -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-background p-6 shadow-2xl"><h2 className="text-xl font-semibold">Scanner Setup</h2><ol className="mt-4 list-decimal space-y-2 pl-5 text-sm"><li>Turn on the scanner.</li><li>Connect the USB receiver or pair it in supported HID mode.</li><li>Open this Barcode Scanner page.</li><li>Click Start Scanner.</li><li>Scan a barcode.</li><li>If barcode text appears, the scanner is ready.</li></ol><p className="mt-4 rounded-xl bg-muted p-3 text-sm">If scanning produces no text, verify that the scanner is configured in USB HID / keyboard mode.</p><button onClick={()=>setHelp(false)} className="mt-4 h-11 w-full rounded-xl bg-primary font-semibold text-primary-foreground">Close</button></section></>}
  </div>;
}
