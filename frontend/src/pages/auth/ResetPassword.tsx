import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authService } from '@/services/auth';
import { getApiErrorMessage } from '@/lib/api-error';

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState(''); const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(''); setMessage('');
    if (!token) { setError('This password reset link is invalid.'); return; }
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    try { setBusy(true); setMessage(await authService.resetPassword(token, password)); setPassword(''); setConfirm(''); }
    catch (reason) { setError(getApiErrorMessage(reason)); } finally { setBusy(false); } };
  return <div><h1 className="text-3xl font-semibold">Reset password</h1><p className="mt-2 text-sm text-muted-foreground">Choose a strong password with upper and lower case letters, a number, and a symbol.</p>
    <form onSubmit={submit} className="mt-8 space-y-5">{error&&<p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}{message&&<p role="status" className="rounded-lg bg-emerald-500/10 p-3 text-sm text-emerald-700">{message} <Link to="/login" className="font-semibold underline">Sign in</Link></p>}
      <label className="block text-sm font-medium">New password<input value={password} onChange={event=>setPassword(event.target.value)} type="password" autoComplete="new-password" minLength={12} maxLength={128} required className="mt-2 h-11 w-full rounded-lg border bg-background px-3"/></label>
      <label className="block text-sm font-medium">Confirm password<input value={confirm} onChange={event=>setConfirm(event.target.value)} type="password" autoComplete="new-password" minLength={12} maxLength={128} required className="mt-2 h-11 w-full rounded-lg border bg-background px-3"/></label>
      <button disabled={busy} className="h-11 w-full rounded-lg bg-primary font-semibold text-primary-foreground disabled:opacity-60">{busy?'Resetting…':'Reset password'}</button></form></div>;
}
