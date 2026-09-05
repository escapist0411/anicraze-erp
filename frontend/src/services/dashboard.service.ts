import { getData } from './api';
import type { OwnerDashboard } from '@/types/dashboard';
import type { QueryParams } from '@/types/api';
export const dashboardService={ owner:(params:QueryParams={})=>getData<OwnerDashboard>('/dashboard/owner',params) };
