import { useQuery } from '@tanstack/react-query';
import { inventoryService } from '@/services/inventory';
import { queryKeys } from '@/lib/query-keys';
import type { Product } from '@/components/inventory/data';
import type { InventoryRecord } from '@/types/inventory';
export function useInventory(params:Record<string,string|number|undefined>={page:1,page_size:50}) {return useQuery({queryKey:queryKeys.inventory(params),queryFn:()=>inventoryService.list(params),staleTime:30_000});}
export function inventoryItems(data:Awaited<ReturnType<typeof inventoryService.list>>|undefined):InventoryRecord[]{return !data?[]:Array.isArray(data)?data:data.items}
export function toInventoryProduct(row:InventoryRecord):Product{return {id:row.id,sku:row.sku,barcode:row.barcode??'—',name:row.product_name,category:row.category,brand:row.brand??'—',store:row.store?.name??row.warehouse?.name??'—',purchasePrice:Number(row.average_cost),sellingPrice:Number(row.average_cost),stock:row.available_quantity,minimumStock:row.minimum_stock,status:row.stock_level==='OUT_OF_STOCK'?'Out of stock':row.stock_level==='LOW_STOCK'?'Low stock':'Active',updated:new Date(row.updated_at).toLocaleString('en-IN'),description:'Live inventory record',supplier:'—',hue:'from-indigo-400 to-violet-700'};}
