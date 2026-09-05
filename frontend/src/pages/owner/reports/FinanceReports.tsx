import { AnalyticsHeader } from '@/components/reports/AnalyticsHeader';
import { FilterPanel } from '@/components/reports/FilterPanel';
import { FinanceChart } from '@/components/reports/ReportCharts';
import { GSTSummary, GoalProgress, InsightCard, ReportTable } from '@/components/reports/ReportPanels';
export default function FinanceReports() { return <div className="mx-auto max-w-[1680px] space-y-6"><AnalyticsHeader title="Finance reports" description="Monitor income, expenses, cash flow, GST, outstanding payments, and profitability." /><FilterPanel /><div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]"><div className="space-y-6"><FinanceChart /><ReportTable /></div><aside className="space-y-5"><GSTSummary /><GoalProgress /><InsightCard /></aside></div></div>; }
