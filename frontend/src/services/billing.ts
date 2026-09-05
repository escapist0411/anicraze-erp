import {api,downloadFile,getData} from './api';
import type {Customer,Invoice,POSProduct} from '@/types/billing';
export const posService={
 search:(storeId:string,query:string)=>getData<POSProduct[]>('/billing/search',{store_id:storeId,query}),
 barcode:(storeId:string,barcode:string)=>getData<POSProduct>(`/billing/barcode/${encodeURIComponent(barcode)}`,{store_id:storeId}),
 customers:(query='')=>getData<Customer[]>('/billing/customers',{query:query||undefined}),
 createCustomer:async(payload:{name:string;phone?:string;email?:string;state_code?:string})=>(await api.post('/billing/customers',payload)).data.data as Customer,
 createInvoice:async(payload:unknown)=>(await api.post('/billing',payload)).data.data as Invoice,
 invoices:()=>getData<Invoice[]>('/invoices'),detail:(id:string)=>getData<Invoice>(`/invoices/${id}`),
 cancel:async(id:string,reason:string)=>(await api.post(`/invoices/${id}/cancel`,{reason})).data.data as Invoice,
 pdf:(id:string)=>downloadFile(`/invoices/${id}/pdf`),
};
