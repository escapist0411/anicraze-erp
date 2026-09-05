import { AnalyticsHeader } from '@/components/reports/AnalyticsHeader';
import { FilterPanel } from '@/components/reports/FilterPanel';
import { EmployeeChart, StoreComparison } from '@/components/reports/ReportCharts';
import { GoalProgress, InsightCard } from '@/components/reports/ReportPanels';
export default function EmployeeReports() { return <div className="mx-auto max-w-[1680px] space-y-6"><AnalyticsHeader title="Employee reports" description="Review sales by employee, invoicing, attendance, productivity, and top performers." /><FilterPanel /><div className="grid gap-6 xl:grid-cols-2"><EmployeeChart /><StoreComparison /></div><div className="grid gap-6 xl:grid-cols-2"><GoalProgress /><InsightCard /></div></div>; }
