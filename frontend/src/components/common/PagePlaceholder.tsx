import { motion } from 'framer-motion';
import { Construction, Sparkles } from 'lucide-react';

export function PagePlaceholder({ title, description }: { title: string; description: string }) {
  return <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mx-auto grid min-h-[55vh] max-w-2xl place-items-center text-center">
    <div className="rounded-3xl border bg-card p-8 shadow-sm sm:p-12"><div className="mx-auto mb-5 grid size-14 place-items-center rounded-2xl bg-primary text-primary-foreground"><Construction className="size-6" /></div>
      <p className="mb-2 flex items-center justify-center gap-2 text-xs font-semibold tracking-[0.16em] text-primary uppercase"><Sparkles className="size-3.5" /> Phase one foundation</p>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1><p className="mt-3 text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  </motion.section>;
}
