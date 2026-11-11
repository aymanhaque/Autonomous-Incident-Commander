import { useState, useRef, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import PrimaryButton from '../primitives/PrimaryButton'

interface Props {
  isOpen: boolean
  onClose: () => void
  onConfirm: (reason: string) => void
  loading?: boolean
}

export default function DenyReasonModal({ isOpen, onClose, onConfirm, loading = false }: Props) {
  const [reason, setReason] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (isOpen) {
      setReason('')
      setTimeout(() => textareaRef.current?.focus(), 50)
    }
  }, [isOpen])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (reason.trim()) onConfirm(reason.trim())
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/30 z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1,    y: 0 }}
            exit={{   opacity: 0, scale: 0.96,  y: 8 }}
            transition={{ duration: 0.18 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="deny-modal-title"
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md bg-bg-elevated border border-border rounded-xl shadow-lg p-6"
          >
            <h3 id="deny-modal-title" className="text-base font-semibold text-text-primary mb-1">
              Deny plan
            </h3>
            <p className="text-sm text-text-secondary mb-4">
              Provide a reason. This will be written to the audit log.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <textarea
                ref={textareaRef}
                value={reason}
                onChange={e => setReason(e.target.value)}
                rows={4}
                required
                placeholder="e.g. Blast radius too large — coordinate with on-call first."
                className="w-full resize-none rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder-text-tertiary focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-transparent transition-all"
              />
              <div className="flex justify-end gap-3">
                <PrimaryButton type="button" variant="ghost" onClick={onClose} disabled={loading}>
                  Cancel
                </PrimaryButton>
                <PrimaryButton type="submit" variant="danger" disabled={loading || !reason.trim()}>
                  {loading ? 'Denying…' : 'Deny plan'}
                </PrimaryButton>
              </div>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
