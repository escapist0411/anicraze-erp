import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Eye, EyeOff, LoaderCircle, LockKeyhole, Mail } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { dashboardPathFor } from '@/lib/roles';
import { getApiErrorMessage } from '@/lib/api-error';
import { authService } from '@/services/auth';

const schema = z.object({ email: z.string().email('Enter a valid work email.'), password: z.string().min(1, 'Password is required.'), rememberMe: z.boolean() });
type FormValues = z.infer<typeof schema>;

export function LoginForm() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [apiError, setApiError] = useState('');
  const [notice, setNotice] = useState('');
  const [isResetting, setIsResetting] = useState(false);
  const { register, handleSubmit, setError, getValues, formState: { errors, isSubmitting } } = useForm<FormValues>({ defaultValues: { email: '', password: '', rememberMe: true } });

  const submit = async (values: FormValues) => {
    const result = schema.safeParse(values);
    if (!result.success) { result.error.issues.forEach((issue) => setError(issue.path[0] as keyof FormValues, { message: issue.message })); return; }
    try { setApiError(''); setNotice(''); const user = await login(result.data); navigate(dashboardPathFor(user.role), { replace: true }); }
    catch (error) { setApiError(getApiErrorMessage(error)); }
  };
  const forgotPassword = async () => {
    const email = getValues('email');
    if (!z.string().email().safeParse(email).success) { setError('email', { message: 'Enter your work email first.' }); return; }
    try { setApiError(''); setNotice(''); setIsResetting(true); setNotice(await authService.forgotPassword(email)); }
    catch (error) { setApiError(getApiErrorMessage(error)); }
    finally { setIsResetting(false); }
  };

  return <form onSubmit={handleSubmit(submit)} className="space-y-5" noValidate>
    {apiError && <div role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">{apiError}</div>}
    {notice && <div role="status" className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">{notice}</div>}
    <label className="block space-y-2"><span className="text-sm font-medium">Work email</span><span className="relative block"><Mail className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" /><input {...register('email')} type="email" autoComplete="email" placeholder="you@company.com" className="h-11 w-full rounded-lg border bg-background pr-3 pl-10 text-sm outline-none transition focus:border-primary focus:ring-3 focus:ring-primary/15" /></span>{errors.email && <span className="text-xs text-destructive">{errors.email.message}</span>}</label>
    <label className="block space-y-2"><span className="flex items-center justify-between text-sm font-medium">Password <button type="button" disabled={isResetting} onClick={forgotPassword} className="font-medium text-primary hover:underline disabled:cursor-wait disabled:opacity-60">{isResetting ? 'Sending…' : 'Forgot password?'}</button></span><span className="relative block"><LockKeyhole className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" /><input {...register('password')} type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" className="h-11 w-full rounded-lg border bg-background pr-10 pl-10 text-sm outline-none transition focus:border-primary focus:ring-3 focus:ring-primary/15" /><button type="button" onClick={() => setShowPassword((shown) => !shown)} className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground hover:text-foreground" aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></span>{errors.password && <span className="text-xs text-destructive">{errors.password.message}</span>}</label>
    <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground"><input {...register('rememberMe')} type="checkbox" className="size-4 rounded border-input accent-primary" /> Keep me signed in</label>
    <button disabled={isSubmitting} className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60">{isSubmitting && <LoaderCircle className="size-4 animate-spin" />}{isSubmitting ? 'Signing in…' : 'Sign in securely'}</button>
  </form>;
}
