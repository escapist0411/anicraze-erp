import { api, downloadFile, getData } from './api';
import type { Page, QueryParams } from '@/types/api';
import type { BarcodeResult, InventoryAlert, InventoryLocation, InventoryRecord, InventorySummary, InventoryTransaction, StockPdfImportPreview, StockReceipt, StockTransfer } from '@/types/inventory';
export const inventoryService={
 list:(params:QueryParams={})=>getData<Page<InventoryRecord>|InventoryRecord[]>('/inventory',params),
 stockReport:()=>getData<InventoryRecord[]>('/inventory/reports/stock'),
 summary:()=>getData<InventorySummary>('/inventory/analytics/summary'),
 stores:()=>getData<InventoryLocation[]>('/stores'),warehouses:()=>getData<InventoryLocation[]>('/warehouses'),
 transactions:(inventoryId?:string)=>getData<InventoryTransaction[]>('/inventory/transactions',{inventory_id:inventoryId}),
 ledger:(inventoryId?:string)=>getData<InventoryTransaction[]>('/inventory/ledger',{inventory_id:inventoryId}),
 alerts:()=>getData<InventoryAlert[]>('/inventory-alerts',{status:'OPEN'}),transfers:()=>getData<StockTransfer[]>('/stock-transfers'),
 transferDetail:(id:string)=>getData<StockTransfer>(`/stock-transfers/${id}`),
 transitionTransfer:async(id:string,status:string,reason?:string)=>(await api.patch(`/stock-transfers/${id}/status`,{status,reason})).data.data,
 pickTransfer:async(id:string,items:{item_id:string;picked_quantity:number}[])=>(await api.post(`/stock-transfers/${id}/pick`,{items})).data.data,
 receiveTransfer:async(id:string,items:{item_id:string;received_quantity:number;damaged_quantity:number;excess_quantity:number;note?:string}[],notes?:string)=>(await api.post(`/stock-transfers/${id}/receive`,{items,notes})).data.data,
 exportCsv:()=>downloadFile('/inventory/export'),
 stockIn:async(id:string,payload:unknown)=>(await api.post(`/inventory/${id}/stock-in`,payload)).data.data,
 markDamaged:async(id:string,payload:unknown)=>(await api.post(`/inventory/${id}/damage`,payload)).data.data,
 adjust:async(payload:unknown)=>(await api.post('/stock-adjustments',payload)).data.data,
 transfer:async(payload:unknown)=>(await api.post('/stock-transfers',payload)).data.data,
 transferReceipt:(id:string)=>downloadFile(`/stock-transfers/${id}/receipt`),
 generateBarcode:async(productId:string,regenerate=false,format='CODE128')=>{const result=(await api.post<{data:BarcodeResult}>(`/products/${productId}/barcode`,{regenerate,format})).data.data;if(result.image_url&&api.defaults.baseURL)result.image_url=new URL(result.image_url,new URL(api.defaults.baseURL).origin).toString();return result},
 receipts:()=>getData<StockReceipt[]>('/stock-receipts'),
 receipt:(id:string)=>getData<StockReceipt>(`/stock-receipts/${id}`),
 createReceipt:async(payload:unknown)=>(await api.post<{data:StockReceipt}>('/stock-receipts',payload)).data.data,
 scanReceipt:async(id:string,code:string)=>(await api.post<{data:StockReceipt}>(`/stock-receipts/${id}/scan`,{code})).data.data,
 finalizeReceipt:async(id:string)=>(await api.post<{data:StockReceipt}>(`/stock-receipts/${id}/finalize`)).data.data,
 importReceiptPdf:async(file:File)=>{const form=new FormData();form.append('file',file);return (await api.post<{data:StockPdfImportPreview}>('/stock-receipts/import-pdf',form,{headers:{'Content-Type':'multipart/form-data'}})).data.data},
 };
