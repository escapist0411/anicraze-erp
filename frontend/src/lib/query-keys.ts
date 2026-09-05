export const queryKeys = {
  auth: { me: ['auth','me'] as const, sessions: ['auth','sessions'] as const },
  dashboard: (filters: object = {}) => ['dashboard', filters] as const,
  products: (params: object = {}) => ['products', params] as const,
  catalog: (type: string, params: object = {}) => ['catalog', type, params] as const,
  inventory: (params: object = {}) => ['inventory', params] as const,
  billing: (params: object = {}) => ['billing', params] as const,
  customers: (params: object = {}) => ['customers', params] as const,
  procurement: (resource: string, params: object = {}) => ['procurement', resource, params] as const,
  employees: (resource: string, params: object = {}) => ['employees', resource, params] as const,
  reports: (type: string, params: object = {}) => ['reports', type, params] as const,
  stores: (resource: string, params: object = {}) => ['stores', resource, params] as const,
};
