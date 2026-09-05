import { PayrollCard } from '@/components/employees/HRPanels';
import { EmployeeTable } from '@/components/employees/EmployeeTable';
export default function Payroll() { return <div className="mx-auto max-w-[1500px] space-y-6"><section><p className="text-sm text-muted-foreground">Compensation operations</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">Payroll management</h2></section><div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]"><PayrollCard /><EmployeeTable /></div></div>; }
