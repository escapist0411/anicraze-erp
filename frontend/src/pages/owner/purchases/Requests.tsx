import { PurchaseRequestForm } from '@/components/purchases/PurchasePanels';
import { PurchaseTable } from '@/components/purchases/PurchaseTables';
export default function Requests() { return <div className="mx-auto max-w-[1500px] space-y-6"><section><p className="text-sm text-muted-foreground">Procurement workflow</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Purchase requests</h2></section><div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]"><PurchaseTable /><PurchaseRequestForm /></div></div>; }
