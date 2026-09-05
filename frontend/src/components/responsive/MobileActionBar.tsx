import type { ReactNode } from 'react';
export function MobileActionBar({children}:{children:ReactNode}){return <div className="sticky bottom-0 z-20 -mx-4 mt-6 flex min-h-16 gap-2 border-t bg-background/95 p-3 pb-[max(.75rem,env(safe-area-inset-bottom))] backdrop-blur sm:static sm:mx-0 sm:min-h-0 sm:border-0 sm:bg-transparent sm:p-0">{children}</div>}
