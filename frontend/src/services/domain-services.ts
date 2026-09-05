import { api, getData } from './api';
import type { QueryParams } from '@/types/api';
const resource=(base:string)=>({list:(params:QueryParams={})=>getData<unknown[]>(base,params),get:(id:string)=>getData<unknown>(`${base}/${id}`),create:async(payload:unknown)=>(await api.post(base,payload)).data.data,update:async(id:string,payload:unknown)=>(await api.patch(`${base}/${id}`,payload)).data.data,remove:(id:string)=>api.delete(`${base}/${id}`)});
export const catalogServices={categories:resource('/categories'),brands:resource('/brands'),anime:resource('/anime'),characters:resource('/characters')};
export const billingService={invoices:resource('/billing/invoices'),createInvoice:async(payload:unknown)=>(await api.post('/billing/invoices',payload)).data.data,customers:resource('/customers')};
export const crmServices={customers:resource('/customers'),memberships:resource('/memberships'),returns:resource('/sales-returns'),refunds:resource('/customer-refunds')};
export const procurementServices={suppliers:resource('/suppliers'),requests:resource('/purchase-requests'),orders:resource('/purchase-orders'),grns:{...resource('/grns'),submit:async(id:string)=>(await api.post(`/grns/${id}/submit`)).data.data,complete:async(id:string)=>(await api.post(`/grns/${id}/complete`)).data.data,cancel:async(id:string)=>(await api.post(`/grns/${id}/cancel`)).data.data},invoices:resource('/supplier-invoices'),payments:resource('/supplier-payments')};
export const hrServices={employees:resource('/employees'),attendance:resource('/attendance'),shifts:resource('/shifts'),leave:resource('/leave/requests'),payroll:resource('/payroll/runs')};
export const locationServices={stores:resource('/stores'),warehouses:resource('/warehouses'),transfers:resource('/stock-transfers')};
