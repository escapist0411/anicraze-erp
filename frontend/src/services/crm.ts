import {api,getData} from './api';
import type {Communication} from '@/types/crm';
export const crmService={
 invoiceCommunications:(id:string)=>getData<Communication[]>(`/invoices/${id}/communications`),
 sendInvoice:async(invoiceId:string)=>(await api.post('/communications/whatsapp/send',{invoice_id:invoiceId})).data.data as Communication,
 retry:async(id:string)=>(await api.post(`/communications/${id}/retry`)).data.data as Communication,
 whatsappSettings:()=>getData<{enabled:boolean;provider:string;configured:boolean;template:string;language:string}>('/communications/whatsapp/settings'),
};
