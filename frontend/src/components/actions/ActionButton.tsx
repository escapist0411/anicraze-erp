import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  loading?: boolean;
  unavailableReason?: string;
}

/** Shared action contract: unavailable actions are disabled and always explain why. */
export function ActionButton({ children, loading = false, unavailableReason, disabled, title, ...props }: Props) {
  const isDisabled = disabled || loading || Boolean(unavailableReason);
  return <button type="button" {...props} disabled={isDisabled} aria-busy={loading || undefined} title={unavailableReason ?? title}>
    {loading ? 'Working…' : children}
  </button>;
}
