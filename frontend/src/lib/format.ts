const money=new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2});
export const formatCurrency=(value:string|number|null|undefined)=>money.format(Number(value??0));
export const formatPercentage=(value:string|number|null|undefined)=>`${Number(value??0).toFixed(2)}%`;
export const formatDate=(value:string)=>new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeZone:'Asia/Kolkata'}).format(new Date(value));
export const formatDateTime=(value:string)=>new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Kolkata'}).format(new Date(value));
export const parseDecimalDisplay=(value:string|number|null|undefined)=>String(value??'0');
