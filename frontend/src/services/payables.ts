import {api,getData} from './api';
import type {PayableSummary,PurchasePayable} from '@/types/payables';
export const payableService={
 list:(status?:string)=>getData<PurchasePayable[]>('/purchase-payables',status?{status}:{}),
 summary:()=>getData<PayableSummary>('/purchase-payables/summary'),
 create:async(payload:unknown)=>(await api.post<{data:PurchasePayable}>('/purchase-payables',payload)).data.data,
 payment:async(id:string,payload:unknown)=>(await api.post<{data:PurchasePayable}>(`/purchase-payables/${id}/payments`,payload)).data.data,
 reminder:async(id:string,remind_at:string,idempotency_key:string)=>(await api.post<{data:PurchasePayable}>(`/purchase-payables/${id}/reminders`,{remind_at,idempotency_key})).data.data,
 update:async(id:string,payload:unknown)=>(await api.patch<{data:PurchasePayable}>(`/purchase-payables/${id}`,payload)).data.data,
};
