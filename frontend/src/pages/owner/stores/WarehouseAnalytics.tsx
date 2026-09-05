import { AnalyticsChart, WarehouseCard } from '@/components/warehouses/WarehouseComponents';
import { AlertCard, TransferTimeline } from '@/components/transfers/TransferComponents';
export default function WarehouseAnalytics() { return <div className="mx-auto max-w-[1600px] space-y-6"><section><p className="text-sm text-muted-foreground">Operational intelligence</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Warehouse analytics</h2></section><div className="grid gap-6 xl:grid-cols-2"><AnalyticsChart /><AlertCard /></div><WarehouseCard /><TransferTimeline /></div>; }
