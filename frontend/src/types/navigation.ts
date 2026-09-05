import type { LucideIcon } from 'lucide-react';
import type { Role } from './auth';

export interface NavigationItem {
  label: string;
  to: string;
  icon: LucideIcon;
  roles: Role[];
  permission?: string;
}
