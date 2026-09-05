import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
export function ResponsiveFormGrid({children,columns=2,className}:{children:ReactNode;columns?:2|3;className?:string}){return <div className={cn('grid min-w-0 grid-cols-1 gap-4',columns===2?'sm:grid-cols-2':'sm:grid-cols-2 xl:grid-cols-3',className)}>{children}</div>}
