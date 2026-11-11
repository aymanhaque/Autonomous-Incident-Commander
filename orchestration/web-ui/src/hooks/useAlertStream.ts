import { useState, useRef } from 'react'

export type StreamPhase =
  | 'idle'
  | 'parsing'
  | 'generating'
  | 'validating'
  | 'classifying'
  | 'done'
  | 'error'

export interface ParsedAlert {
  alertname: string
  namespace: string
  pod?: string
  severity: string
  description: string
}

export interface StreamState {
  phase: StreamPhase
  alertName: string
  parsedAlert: ParsedAlert | null
  hclBuffer: string      // tokens accumulate here while generating
  hclFinal: string       // cleaned plan, set on plan_complete
  remediationSummary: string
  validationPassed: boolean | null
  riskScore: string      // "Low" | "Medium" | "High" | ""
  riskReason: string
  error: string
}

const INITIAL: StreamState = {
  phase: 'idle',
  alertName: '',
  parsedAlert: null,
  hclBuffer: '',
  hclFinal: '',
  remediationSummary: '',
  validationPassed: null,
  riskScore: '',
  riskReason: '',
  error: '',
}

type RawEvent =
  | { type: 'alert_parsed'; data: { alertname?: string; namespace?: string; pod?: string; severity?: string; description?: string; status?: string } }
  | { type: 'token';        data: { content: string } }
  | { type: 'plan_complete'; data: { plan: string } }
  | { type: 'summary';      data: { content: string } }
  | { type: 'validation';   data: { passed: boolean } }
  | { type: 'risk';         data: { score: string; reason: string } }
  | { type: 'error';        data: { message: string } }
  | { type: 'done';         data: Record<string, never> }

export function useAlertStream() {
  const [state, setState] = useState<StreamState>(INITIAL)
  const abort = useRef<AbortController | null>(null)

  async function start(payload: object) {
    abort.current?.abort()
    const ctrl = new AbortController()
    abort.current = ctrl

    setState({ ...INITIAL, phase: 'parsing' })

    try {
      const res = await fetch('/agent/generate-plan/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      })

      if (!res.ok || !res.body) {
        throw new Error(`Agent returned ${res.status}`)
      }

      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''

        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          try {
            const ev: RawEvent = JSON.parse(line.slice(5).trim())
            apply(ev)
          } catch {
            // malformed chunk — skip
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setState(s => ({ ...s, phase: 'error', error: String(err) }))
      }
    }
  }

  function stop() {
    abort.current?.abort()
    setState(s => ({ ...s, phase: 'idle' }))
  }

  function reset() {
    abort.current?.abort()
    setState(INITIAL)
  }

  function apply(ev: RawEvent) {
    setState(s => {
      switch (ev.type) {
        case 'alert_parsed': {
          const name = ev.data.alertname ?? 'Unknown'
          const ns   = ev.data.namespace ?? 'unknown'
          return {
            ...s,
            phase: 'generating',
            alertName: name,
            parsedAlert: {
              alertname:   name,
              namespace:   ns,
              pod:         ev.data.pod,
              severity:    ev.data.severity ?? 'unknown',
              description: ev.data.description ?? '',
            },
          }
        }
        case 'token':
          return { ...s, hclBuffer: s.hclBuffer + ev.data.content }
        case 'plan_complete':
          return { ...s, phase: 'validating', hclFinal: ev.data.plan }
        case 'summary':
          return { ...s, remediationSummary: ev.data.content }
        case 'validation':
          return { ...s, phase: 'classifying', validationPassed: ev.data.passed }
        case 'risk':
          return { ...s, phase: 'done', riskScore: ev.data.score, riskReason: ev.data.reason }
        case 'error':
          return { ...s, phase: 'error', error: ev.data.message }
        default:
          return s
      }
    })
  }

  return { state, start, stop, reset }
}
