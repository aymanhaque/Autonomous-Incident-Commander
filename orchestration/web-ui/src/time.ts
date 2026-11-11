export function relativeTime(iso: string, now: number = Date.now()): string {
  const diffMs = now - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(diffMs / 3_600_000)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(diffMs / 86_400_000)}d ago`
}

export interface Countdown {
  text: string
  expired: boolean
  urgent: boolean
}

export function countdown(iso: string, now: number = Date.now()): Countdown {
  const ms = new Date(iso).getTime() - now
  if (ms <= 0) return { text: 'EXPIRED', expired: true, urgent: true }
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  const text = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return { text, expired: false, urgent: ms < 5 * 60 * 1000 }
}

export function clockUTC(d: Date): string {
  return d.toISOString().slice(11, 19)
}
