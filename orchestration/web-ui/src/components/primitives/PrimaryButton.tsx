import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'ghost' | 'danger'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  children: ReactNode
}

const variants: Record<Variant, string> = {
  primary: 'bg-accent-500 text-white hover:bg-accent-600 shadow-sm hover:shadow focus:ring-accent-500',
  ghost:   'bg-transparent text-text-primary hover:bg-bg-tertiary border border-border focus:ring-text-secondary',
  danger:  'bg-danger-500 text-white hover:bg-danger-600 shadow-sm hover:shadow focus:ring-danger-500',
}

export default function PrimaryButton({ variant = 'primary', children, className = '', ...rest }: Props) {
  return (
    <button
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
