import { useEffect, useRef, useState } from 'react'
import { hlPromise, HCL_HIGHLIGHT_OPTS, type HL } from '../../lib/highlighter'

const STREAM_DEBOUNCE_MS = 80

interface Props {
  code: string
  isStreaming: boolean
}

export default function StreamingCodeBlock({ code, isStreaming }: Props) {
  const [html, setHtml] = useState<string | null>(null)
  const pending       = useRef(code)
  const timer         = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isStreamingRef = useRef(isStreaming)
  const hlRef         = useRef<HL | null>(null)

  function flush() {
    const hl = hlRef.current
    if (!hl) return
    try {
      setHtml(hl.codeToHtml(pending.current, HCL_HIGHLIGHT_OPTS))
    } catch {
      // Partial / incomplete HCL mid-stream — keep previous HTML
    }
  }

  function schedule(c: string) {
    pending.current = c
    if (timer.current) { clearTimeout(timer.current); timer.current = null }
    timer.current = setTimeout(() => {
      timer.current = null
      flush()
    }, isStreamingRef.current ? STREAM_DEBOUNCE_MS : 0)
  }

  useEffect(() => {
    hlPromise.then(hl => {
      hlRef.current = hl
      flush()
    })
    return () => { if (timer.current) clearTimeout(timer.current) }
  }, [])

  useEffect(() => {
    pending.current = code
    if (hlRef.current) schedule(code)
  }, [code])

  useEffect(() => {
    isStreamingRef.current = isStreaming
    if (!isStreaming && hlRef.current) {
      if (timer.current) { clearTimeout(timer.current); timer.current = null }
      flush()
    }
  }, [isStreaming])

  const cursor = isStreaming ? (
    <span className="inline-block w-[7px] h-[1.1em] bg-accent-500 ml-0.5 align-text-bottom animate-pulse" />
  ) : null

  if (html) {
    return (
      <div className="streaming-hcl font-mono text-sm leading-relaxed">
        <div dangerouslySetInnerHTML={{ __html: html }} />
        {cursor}
      </div>
    )
  }

  const lines = code.split('\n')
  return (
    <div className="font-mono text-sm leading-relaxed">
      {lines.map((line, i) => (
        <div key={i} className="flex min-h-[1.5em]">
          <span className="select-none w-[3.25rem] shrink-0 text-right pr-3 text-text-tertiary opacity-40 text-xs leading-relaxed pt-[1px]">
            {i + 1}
          </span>
          <span className="flex-1 text-text-primary whitespace-pre">{line}</span>
        </div>
      ))}
      {cursor && (
        <div className="flex">
          <span className="w-[3.25rem] shrink-0" />
          {cursor}
        </div>
      )}
    </div>
  )
}
