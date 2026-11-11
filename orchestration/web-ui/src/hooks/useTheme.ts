import { useState, useEffect, useRef } from 'react'

type Theme = 'light' | 'dark' | 'system'
type Accent = 'blue' | 'indigo' | 'emerald'

const THEME_KEY = 'aic-theme'
const ACCENT_KEY = 'aic-accent'

function applyTheme(t: Theme) {
  const dark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>('system')
  const [accent, setAccent] = useState<Accent>('blue')
  const themeRef = useRef<Theme>('system')

  useEffect(() => {
    if (typeof window === 'undefined') return

    const savedTheme = (localStorage.getItem(THEME_KEY) as Theme) ?? 'light'
    const savedAccent = (localStorage.getItem(ACCENT_KEY) as Accent) ?? 'blue'

    themeRef.current = savedTheme
    setTheme(savedTheme)
    setAccent(savedAccent)
    document.documentElement.setAttribute('data-accent', savedAccent)
    applyTheme(savedTheme)

    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => { if (themeRef.current === 'system') applyTheme('system') }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  function updateTheme(t: Theme) {
    themeRef.current = t
    setTheme(t)
    localStorage.setItem(THEME_KEY, t)
    applyTheme(t)
  }

  function updateAccent(a: Accent) {
    setAccent(a)
    localStorage.setItem(ACCENT_KEY, a)
    document.documentElement.setAttribute('data-accent', a)
  }

  return { theme, accent, updateTheme, updateAccent }
}
