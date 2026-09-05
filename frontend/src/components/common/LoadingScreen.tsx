import { LoaderCircle } from 'lucide-react';
export function LoadingScreen() { return <div className="grid min-h-screen place-items-center bg-background"><div className="flex items-center gap-3 text-sm text-muted-foreground"><LoaderCircle className="size-5 animate-spin text-primary" /> Restoring your workspace…</div></div>; }
