import { AnalyticsHeader } from '@/components/reports/AnalyticsHeader';
import { FilterPanel } from '@/components/reports/FilterPanel';
import { CustomerChart } from '@/components/reports/ReportCharts';
import { GoalProgress, InsightCard, ReportTable } from '@/components/reports/ReportPanels';
export default function CustomerReports() { return <div className="mx-auto max-w-[1680px] space-y-6"><AnalyticsHeader title="Customer reports" description="Understand top customers, retention, lifetime value, purchase frequency, and memberships." /><FilterPanel /><div className="grid gap-6 xl:grid-cols-2"><CustomerChart /><GoalProgress /></div><ReportTable /><InsightCard /></div>; }
