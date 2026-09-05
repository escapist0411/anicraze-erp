export interface User {
  id: number;
  name: string;
  role: 'owner' | 'manager' | 'employee';
}
