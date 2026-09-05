import { AnalyticsHeader } from '@/components/reports/AnalyticsHeader';
import { FilterPanel } from '@/components/reports/FilterPanel';
import { InventoryChart, StoreComparison } from '@/components/reports/ReportCharts';
import { GoalProgress, InsightCard } from '@/components/reports/ReportPanels';
export default function InventoryReports() { return <div className="mx-auto max-w-[1680px] space-y-6"><AnalyticsHeader title="Inventory reports" description="Track inventory value, stock aging, movement, category and warehouse distribution." /><FilterPanel /><div className="grid gap-6 xl:grid-cols-2"><InventoryChart /><StoreComparison /></div><div className="grid gap-6 xl:grid-cols-2"><InsightCard /><GoalProgress /></div></div>; }
