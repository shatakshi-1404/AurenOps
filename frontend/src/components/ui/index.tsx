import {
  forwardRef, useEffect, useRef, useState,
  type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode,
  type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'

const variants = {
  primary: 'bg-violet text-white hover:bg-violet/90 shadow-sm',
  outline: 'border border-border bg-panel2 hover:bg-border/60',
  ghost: 'hover:bg-panel2 text-muted hover:text-fg',
  danger: 'bg-bad/15 text-bad border border-bad/30 hover:bg-bad/25',
  success: 'bg-ok/15 text-ok border border-ok/30 hover:bg-ok/25',
}
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants; size?: 'sm' | 'md' | 'lg'; loading?: boolean
}
export const Button = forwardRef<HTMLButtonElement, BtnProps>(
  ({ variant = 'primary', size = 'md', loading, className, children, disabled, ...p }, ref) => (
    <button
      ref={ref} disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:pointer-events-none disabled:opacity-50',
        size === 'sm' ? 'h-8 px-3 text-xs' : size === 'lg' ? 'h-11 px-5 text-sm' : 'h-9 px-4 text-sm',
        variants[variant], className,
      )}
      {...p}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  ),
)

export const Card = ({ className, children }: { className?: string; children: ReactNode }) => (
  <div className={cn('rounded-xl border border-border bg-panel', className)}>{children}</div>
)

const tones = {
  neutral: 'bg-panel2 text-muted border-border', violet: 'bg-violet/15 text-violet border-violet/30',
  cyan: 'bg-cyan/15 text-cyan border-cyan/30', ok: 'bg-ok/15 text-ok border-ok/30',
  warn: 'bg-warn/15 text-warn border-warn/30', bad: 'bg-bad/15 text-bad border-bad/30',
}
export type Tone = keyof typeof tones
export const Badge = ({ tone = 'neutral', className, children }: { tone?: Tone; className?: string; children: ReactNode }) => (
  <span className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium', tones[tone], className)}>{children}</span>
)

const field = 'w-full rounded-lg border border-border bg-panel2 px-3 text-sm text-fg placeholder:text-muted/70 focus:border-violet focus:outline-none focus:ring-1 focus:ring-violet'
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn(field, 'h-9', className)} {...p} />
))
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn(field, 'py-2', className)} {...p} />
))
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...p }, ref) => (
  <select ref={ref} className={cn(field, 'h-9', className)} {...p} />
))
export const Field = ({ label, error, children }: { label: string; error?: unknown; children: ReactNode }) => {
  const msg = typeof error === 'string' ? error : (error as { message?: string } | undefined)?.message
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-muted">{label}</span>
      {children}
      {msg && <span className="block text-xs text-bad">{msg}</span>}
    </label>
  )
}

export const Skeleton = ({ className }: { className?: string }) => <div className={cn('animate-pulse rounded-lg bg-panel2', className)} />
export const Spinner = () => <Loader2 className="h-5 w-5 animate-spin text-muted" />

export const EmptyState = ({ icon, title, hint, action }: { icon?: ReactNode; title: string; hint?: string; action?: ReactNode }) => (
  <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
    {icon && <div className="mb-1 rounded-full bg-panel2 p-3 text-muted">{icon}</div>}
    <div className="text-sm font-medium">{title}</div>
    {hint && <div className="max-w-sm text-xs text-muted">{hint}</div>}
    {action}
  </div>
)

export function Modal({ open, onClose, title, children, wide, footer }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean; footer?: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={onClose}>
          <motion.div
            className={cn('flex max-h-[88vh] w-full flex-col rounded-2xl border border-border bg-panel shadow-2xl', wide ? 'max-w-3xl' : 'max-w-lg')}
            initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 12, opacity: 0 }}
            onMouseDown={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <h3 className="text-sm font-semibold">{title}</h3>
              <button onClick={onClose} className="text-muted hover:text-fg"><X className="h-4 w-4" /></button>
            </div>
            <div className="overflow-y-auto p-5">{children}</div>
            {footer && <div className="flex justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function Popover({ button, children, align = 'right' }: {
  button: (open: boolean, toggle: () => void) => ReactNode; children: (close: () => void) => ReactNode; align?: 'left' | 'right'
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div ref={ref} className="relative">
      {button(open, () => setOpen((o) => !o))}
      {open && (
        <div className={cn('absolute z-40 mt-2 min-w-[220px] rounded-xl border border-border bg-panel p-1.5 shadow-2xl', align === 'right' ? 'right-0' : 'left-0')}>
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex gap-1 rounded-lg border border-border bg-panel2 p-1">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={cn('rounded-md px-3 py-1.5 text-xs font-medium transition', value === t.id ? 'bg-panel text-fg shadow-sm' : 'text-muted hover:text-fg')}>
          {t.label}
        </button>
      ))}
    </div>
  )
}
