import { useState, useCallback } from 'react'

export interface ToastItem {
  id: number
  message: string
  type: 'info' | 'success' | 'error'
  description?: string
}

let nextId = 0

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const removeToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const addToast = useCallback((
    message: string,
    type: ToastItem['type'] = 'info',
    description?: string,
    duration = 3500,
  ) => {
    const id = nextId++
    setToasts(prev => [...prev, { id, message, type, description }])
    if (duration > 0) setTimeout(() => removeToast(id), duration)
    return id
  }, [removeToast])

  return { toasts, addToast, removeToast }
}
