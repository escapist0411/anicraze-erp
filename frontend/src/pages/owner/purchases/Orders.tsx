import { PurchaseOrderDetails } from '@/components/purchases/PurchasePanels';
import { PurchaseOrderTable } from '@/components/purchases/PurchaseTables';
export default function Orders() { return <div className="mx-auto max-w-[1500px] space-y-6"><section><p className="text-sm text-muted-foreground">Supplier commitments</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Purchase orders</h2></section><PurchaseOrderTable /><PurchaseOrderDetails /></div>; }
