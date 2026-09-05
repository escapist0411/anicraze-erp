import { LoyaltyCard, CustomerInsights } from '@/components/customers/CustomerPanels';
import { AnalyticsChart } from '@/components/customers/CustomerPanels';
export default function Loyalty() { return <div className="mx-auto max-w-[1400px] space-y-6"><section><p className="text-sm text-muted-foreground">Customer rewards</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Loyalty program</h2></section><div className="grid gap-6 xl:grid-cols-2"><LoyaltyCard /><AnalyticsChart /></div><CustomerInsights /></div>; }
