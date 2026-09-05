import {api,getData} from './api';
import type {Communication,CRMCustomer,CustomerInvoice,LoyaltyAccount,LoyaltyTransaction,Membership,MembershipTier} from '@/types/crm';
export const crmService={
 dashboard:()=>getData<{total_customers:number;loyalty_members:number;total_lifetime_value:number;average_lifetime_value:number}>('/crm/dashboard'),
 customers:(search='')=>getData<CRMCustomer[]>('/customers',{search:search||undefined}),customer:(id:string)=>getData<CRMCustomer>(`/customers/${id}`),
 invoices:(id:string)=>getData<CustomerInvoice[]>(`/customers/${id}/invoices`),returns:(id:string)=>getData<Record<string,unknown>[]>(`/customers/${id}/returns`),refunds:(id:string)=>getData<Record<string,unknown>[]>(`/customers/${id}/refunds`),
 loyalty:(id:string)=>getData<LoyaltyAccount>(`/customers/${id}/loyalty`),loyaltyTransactions:(id:string)=>getData<LoyaltyTransaction[]>(`/customers/${id}/loyalty/transactions`),
 memberships:(id:string)=>getData<Membership[]>(`/customers/${id}/memberships`),tiers:()=>getData<MembershipTier[]>('/memberships/tiers'),
 communications:(id:string)=>getData<Communication[]>(`/customers/${id}/communications`),invoiceCommunications:(id:string)=>getData<Communication[]>(`/invoices/${id}/communications`),
 storeCredit:(id:string)=>getData<{balance:number;transactions:Record<string,unknown>[]}>(`/customers/${id}/store-credit`),notes:(id:string)=>getData<Record<string,unknown>[]>(`/customers/${id}/notes`),
 addNote:async(id:string,content:string)=>(await api.post(`/customers/${id}/notes`,{content,note_type:'GENERAL'})).data.data,
 sendInvoice:async(invoiceId:string)=>(await api.post('/communications/whatsapp/send',{invoice_id:invoiceId})).data.data as Communication,
 retry:async(id:string)=>(await api.post(`/communications/${id}/retry`)).data.data as Communication,
 whatsappSettings:()=>getData<{enabled:boolean;provider:string;configured:boolean;template:string;language:string}>('/communications/whatsapp/settings'),
};
