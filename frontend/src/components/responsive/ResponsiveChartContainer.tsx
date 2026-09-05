import type { ReactNode } from 'react';
export function ResponsiveChartContainer({children}:{children:ReactNode}){return <div className="h-60 min-w-0 sm:h-[300px] xl:h-[340px]">{children}</div>}
