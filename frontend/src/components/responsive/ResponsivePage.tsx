import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
export function ResponsivePage({children,className,narrow=false}:{children:ReactNode;className?:string;narrow?:boolean}){return <div className={cn('mx-auto w-full min-w-0 max-w-full space-y-4 sm:space-y-5 lg:space-y-6',narrow&&'max-w-5xl',className)}>{children}</div>}
