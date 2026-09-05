import { PaymentTable, ProcurementInsights } from '@/components/purchases/PurchasePanels';
export default function Payments() { return <div className="mx-auto max-w-[1500px] space-y-6"><section><p className="text-sm text-muted-foreground">Accounts payable</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Supplier payments</h2></section><PaymentTable /><ProcurementInsights /></div>; }
