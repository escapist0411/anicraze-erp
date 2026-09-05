import { api, getData } from './api';
import type { QueryParams } from '@/types/api';
export type NotificationCategory='INVENTORY'|'TRANSFER'|'PROCUREMENT'|'COMMUNICATION'|'REPORT'|'SYSTEM';
export interface OperationalNotification{id:string;category:NotificationCategory;severity:'INFO'|'WARNING'|'HIGH'|'CRITICAL';title:string;message:string;entity_type?:string;entity_id?:string;action_path?:string;is_read:boolean;is_resolved:boolean;created_at:string;read_at?:string}
export interface NotificationSummary{unread_count:number;active_count:number;critical_count:number;warning_count:number;recent:OperationalNotification[]}
export const notificationsService={list:(params:QueryParams={})=>getData<OperationalNotification[]>('/notifications',params),summary:()=>getData<NotificationSummary>('/notifications/summary'),markRead:async(id:string)=>(await api.post(`/notifications/${id}/read`)).data.data,markAllRead:async()=>(await api.post('/notifications/mark-all-read')).data.data};
