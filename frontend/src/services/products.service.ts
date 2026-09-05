import { api, downloadFile, getData, uploadFile } from './api';
import type { BackendProduct } from '@/types/products';
import type { Page, QueryParams } from '@/types/api';
export interface ImportPreview {total_rows:number;valid_rows:number;invalid_rows:number;created_rows:number;dry_run:boolean;errors:{row:number;field:string|null;message:string}[]}
export interface BarcodeData {product_id:string;sku:string;barcode:string;format:string;image_url:string|null}
const absoluteAsset=(url:string|null)=>url&&api.defaults.baseURL?new URL(url,new URL(api.defaults.baseURL).origin).toString():url;
export const productsService={
 list:(params:QueryParams={})=>getData<Page<BackendProduct>|BackendProduct[]>('/products',params),
 get:(id:string)=>getData<BackendProduct>(`/products/${id}`),
 lookupBarcode:(barcode:string)=>getData<BackendProduct>(`/products/search/barcode/${encodeURIComponent(barcode)}`),
 lookupSku:(sku:string)=>getData<BackendProduct>(`/products/search/sku/${encodeURIComponent(sku)}`),
 create:async(payload:unknown)=>(await api.post(`/products`,payload)).data.data,
 update:async(id:string,payload:unknown)=>(await api.patch(`/products/${id}`,payload)).data.data,
 remove:(id:string)=>api.delete(`/products/${id}`),
 uploadImage:(id:string,file:File)=>{const form=new FormData();form.append('file',file);return uploadFile(`/products/${id}/images`,form)},
 removeImage:(productId:string,imageId:string)=>api.delete(`/products/${productId}/images/${imageId}`),
 getBarcode:async(id:string)=>{const value=await getData<BarcodeData>(`/products/${id}/barcode`);return {...value,image_url:absoluteAsset(value.image_url)}},
 generateBarcode:async(id:string,format:'CODE128'|'EAN13'='CODE128',regenerate=false)=>{const value=(await api.post<{data:BarcodeData}>(`/products/${id}/barcode`,{format,regenerate})).data.data;return {...value,image_url:absoluteAsset(value.image_url)}},
 importCsv:(file:File,dryRun=true)=>{const form=new FormData();form.append('file',file);return uploadFile<ImportPreview>(`/products/import?dry_run=${dryRun}`,form)},
 exportCsv:(params:QueryParams={})=>downloadFile('/products/export',params),
};
