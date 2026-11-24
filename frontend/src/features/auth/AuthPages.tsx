import { useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Button, Card, Field, Input } from '@/components/ui'
import { api } from '@/lib/api'
import { useAuth } from '@/stores/auth'
import type { TokenResponse } from '@/types'

function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="grid min-h-full place-items-center bg-bg p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-violet to-cyan text-lg font-bold text-white">A</div>
          <div className="text-sm font-bold tracking-[0.2em]">AURENOPS</div>
          <div className="mt-1 text-xs text-muted">Your business operations, intelligently orchestrated.</div>
        </div>
        <Card className="p-6">
          <h1 className="text-lg font-semibold">{title}</h1>
          <p className="mb-5 mt-1 text-sm text-muted">{subtitle}</p>
          {children}
        </Card>
      </div>
    </div>
  )
}

const loginSchema = z.object({ email: z.string().email(), password: z.string().min(1, 'Required') })

export function Login() {
  const token = useAuth((s) => s.token)
  const setSession = useAuth((s) => s.setSession)
  const nav = useNavigate()
  const from = (useLocation().state as any)?.from ?? '/'
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(loginSchema) })
  if (token) return <Navigate to={from} replace />
  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your operations command center.">
      <form className="space-y-4" onSubmit={handleSubmit(async (v) => {
        try { setSession(await api.post<TokenResponse>('/auth/login', v)); nav(from, { replace: true }) }
        catch (e: any) { toast.error(e.message) }
      })}>
        <Field label="Email" error={errors.email?.message}><Input type="email" autoComplete="email" {...register('email')} /></Field>
        <Field label="Password" error={errors.password?.message}><Input type="password" autoComplete="current-password" {...register('password')} /></Field>
        <Button className="w-full" loading={isSubmitting}>Sign in</Button>
        <div className="flex justify-between text-xs text-muted">
          <Link to="/forgot-password" className="hover:text-fg">Forgot password?</Link>
          <Link to="/register" className="text-violet">Create account</Link>
        </div>
        <div className="rounded-lg bg-panel2 p-3 text-[11px] text-muted">Demo: operator@demo.com / Passw0rd! (also owner@, admin@, viewer@)</div>
      </form>
    </AuthLayout>
  )
}

const regSchema = z.object({
  full_name: z.string().min(1, 'Required'), org_name: z.string().min(2, 'At least 2 characters'),
  email: z.string().email(), password: z.string().min(8, 'At least 8 characters'),
})

export function Register() {
  const setSession = useAuth((s) => s.setSession)
  const nav = useNavigate()
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(regSchema) })
  return (
    <AuthLayout title="Create your workspace" subtitle="Set up your organization in under a minute.">
      <form className="space-y-4" onSubmit={handleSubmit(async (v) => {
        try { setSession(await api.post<TokenResponse>('/auth/register', v)); nav('/onboarding') }
        catch (e: any) { toast.error(e.message) }
      })}>
        <Field label="Your name" error={errors.full_name?.message}><Input {...register('full_name')} /></Field>
        <Field label="Organization name" error={errors.org_name?.message}><Input {...register('org_name')} /></Field>
        <Field label="Work email" error={errors.email?.message}><Input type="email" {...register('email')} /></Field>
        <Field label="Password" error={errors.password?.message}><Input type="password" {...register('password')} /></Field>
        <Button className="w-full" loading={isSubmitting}>Create workspace</Button>
        <div className="text-center text-xs text-muted">Already have an account? <Link to="/login" className="text-violet">Sign in</Link></div>
      </form>
    </AuthLayout>
  )
}

export function ForgotPassword() {
  const [sent, setSent] = useState(false)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(z.object({ email: z.string().email() })) })
  return (
    <AuthLayout title="Reset your password" subtitle="We'll send a reset link if the account exists.">
      {sent ? <div className="rounded-lg bg-ok/10 p-3 text-sm text-ok">If that account exists, a reset link has been sent.</div> : (
        <form className="space-y-4" onSubmit={handleSubmit(async (v) => { await api.post('/auth/forgot-password', v); setSent(true) })}>
          <Field label="Email" error={errors.email?.message}><Input type="email" {...register('email')} /></Field>
          <Button className="w-full" loading={isSubmitting}>Send reset link</Button>
        </form>
      )}
      <div className="mt-4 text-center text-xs"><Link to="/login" className="text-violet">Back to sign in</Link></div>
    </AuthLayout>
  )
}

export function ResetPassword() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(z.object({ new_password: z.string().min(8, 'At least 8 characters') })),
  })
  return (
    <AuthLayout title="Choose a new password" subtitle="Enter a new password for your account.">
      <form className="space-y-4" onSubmit={handleSubmit(async (v) => {
        try { await api.post('/auth/reset-password', { token: params.get('token') ?? '', ...v }); toast.success('Password updated'); nav('/login') }
        catch (e: any) { toast.error(e.message) }
      })}>
        <Field label="New password" error={errors.new_password?.message}><Input type="password" {...register('new_password')} /></Field>
        <Button className="w-full" loading={isSubmitting}>Update password</Button>
      </form>
    </AuthLayout>
  )
}
