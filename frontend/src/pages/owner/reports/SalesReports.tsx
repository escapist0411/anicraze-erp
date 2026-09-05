import { AnalyticsHeader } from '@/components/reports/AnalyticsHeader';
import { FilterPanel } from '@/components/reports/FilterPanel';
import { SalesChart, StoreComparison } from '@/components/reports/ReportCharts';
import { InsightCard, ReportTable } from '@/components/reports/ReportPanels';
export default function SalesReports() { return <div className="mx-auto max-w-[1680px] space-y-6"><AnalyticsHeader title="Sales reports" description="Study revenue, profit, order volume, stores, categories, and product performance." /><FilterPanel /><div className="grid gap-6 xl:grid-cols-2"><SalesChart /><StoreComparison /></div><ReportTable /><InsightCard /></div>; }
