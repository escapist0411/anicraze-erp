import { EmployeeProfileCard } from '@/components/employees/EmployeeOperations';
import { AttendanceCalendar, LeaveCard } from '@/components/employees/HRPanels';
import { PerformanceCard } from '@/components/employees/EmployeeOperations';
export default function EmployeeProfile() { return <div className="mx-auto max-w-[1300px] space-y-6"><EmployeeProfileCard /><div className="grid gap-6 xl:grid-cols-3"><AttendanceCalendar /><LeaveCard /><PerformanceCard /></div></div>; }
