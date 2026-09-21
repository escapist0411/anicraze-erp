export type PaymentMethod='CASH'|'UPI'|'CARD'|'SPLIT';
export interface POSProduct{inventory_id:string;product_id:string;sku:string;barcode:string|null;name:string;price:number;available_quantity:number}
export interface Customer{id:string;name:string;phone:string|null;email:string|null;address:string|null}
export interface InvoiceItem{id:string;inventory_id:string;product_id:string;sku:string;product_name:string;quantity:number;unit_price:number;discount:number;line_total:number}
export interface Payment{id:string;amount:number;tendered_amount:number|null;change_amount:number;transaction_reference:string|null;status:string}
export interface Invoice{id:string;invoice_number:string;customer_id:string;store_id:string;employee_id:string;store_name:string;store_address:string|null;employee_name:string;employee_code:string|null;customer_name:string;customer_address:string|null;payment_methods:string[];business_contact:string;subtotal:number;discount:number;grand_total:number;payment_status:string;invoice_status:string;notes:string|null;items:InvoiceItem[];payments:Payment[];created_at:string}
