import { PerformanceCard, TaskBoard } from '@/components/employees/EmployeeOperations';
import { DepartmentCard } from '@/components/employees/HRPanels';
export default function Performance() { return <div className="mx-auto max-w-[1500px] space-y-6"><section><p className="text-sm text-muted-foreground">People performance</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Performance management</h2></section><div className="grid gap-6 xl:grid-cols-2"><PerformanceCard /><TaskBoard /></div><DepartmentCard /></div>; }
