import type { Role } from '@/types/auth';

export const roleLabels: Record<Role, string> = {
  owner: 'Owner', manager: 'Manager', employee: 'Employee',
};

export const dashboardPathFor = (role: Role) => `/${role}/dashboard`;
