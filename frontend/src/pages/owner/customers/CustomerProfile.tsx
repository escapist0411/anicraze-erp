import { CustomerProfile as Profile, CommunicationTimeline, CustomerInsights, LoyaltyCard } from '@/components/customers/CustomerPanels';
export default function CustomerProfile() { return <div className="mx-auto max-w-[1400px] space-y-6"><Profile /><div className="grid gap-6 xl:grid-cols-3"><LoyaltyCard /><CommunicationTimeline /><CustomerInsights /></div></div>; }
