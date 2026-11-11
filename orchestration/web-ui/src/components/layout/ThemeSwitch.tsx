import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useTheme } from '../../hooks/useTheme'

type Accent = 'blue' | 'indigo' | 'emerald'
type Theme  = 'light' | 'dark' | 'system'

const accents: { id: Accent; name: string; color: string }[] = [
  { id: 'blue',    name: 'Blue',    color: '#3B82F6' },
  { id: 'indigo',  name: 'Indigo',  color: '#6366F1' },
  { id: 'emerald', name: 'Emerald', color: '#10B981' },
]

const themes: { id: Theme; name: string }[] = [
  { id: 'light',  name: 'Light'  },
  { id: 'dark',   name: 'Dark'   },
  { id: 'system', name: 'System' },
]

export default function ThemeSwitch() {
  const { theme, accent, updateTheme, updateAccent } = useTheme()
  const [open, setOpen] = useState(false)

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Theme settings"
        aria-expanded={open}
        className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-colors"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
        </svg>
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -8 }}
              animate={{ opacity: 1, scale: 1,    y: 0 }}
              exit={{   opacity: 0, scale: 0.95,  y: -8 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-full mt-2 w-60 bg-bg-elevated border border-border rounded-lg shadow-lg z-50 p-4 space-y-4"
            >
              <div>
                <p className="text-xs font-medium text-text-secondary mb-2">Accent</p>
                <div className="flex gap-2">
                  {accents.map(a => (
                    <button
                      key={a.id}
                      onClick={() => updateAccent(a.id)}
                      aria-label={`${a.name} accent`}
                      className={`flex-1 p-2 rounded-lg border-2 transition-all ${
                        accent === a.id ? 'border-accent-500 bg-accent-50' : 'border-border hover:border-accent-200'
                      }`}
                    >
                      <div className="w-full h-5 rounded" style={{ backgroundColor: a.color }} />
                      <span className="text-xs text-text-secondary mt-1 block">{a.name}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs font-medium text-text-secondary mb-2">Theme</p>
                <div className="space-y-1">
                  {themes.map(t => (
                    <button
                      key={t.id}
                      onClick={() => { updateTheme(t.id); setOpen(false) }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                        theme === t.id
                          ? 'bg-accent-50 text-accent-600 font-medium'
                          : 'text-text-primary hover:bg-bg-tertiary'
                      }`}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
