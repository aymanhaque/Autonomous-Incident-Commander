import { useState, useEffect } from 'react'
import { hlPromise, HCL_HIGHLIGHT_OPTS } from '../../lib/highlighter'

const COPY_FEEDBACK_MS = 1800

interface Props {
  hcl: string
}

export default function HclViewer({ hcl }: Props) {
  const [copied,      setCopied]      = useState(false)
  const [highlighted, setHighlighted] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    hlPromise.then(hl => {
      if (!alive) return
      setHighlighted(hl.codeToHtml(hcl, HCL_HIGHLIGHT_OPTS))
    })
    return () => { alive = false }
  }, [hcl])

  function copyToClipboard() {
    navigator.clipboard.writeText(hcl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), COPY_FEEDBACK_MS)
    })
  }

  return (
    <div className="relative rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-bg-tertiary border-b border-border">
        <span className="text-xs font-mono text-text-tertiary">terraform plan · HCL</span>
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors"
          aria-label="Copy HCL to clipboard"
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Copied
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy
            </>
          )}
        </button>
      </div>

      {highlighted != null ? (
        <div className="hcl-viewer p-4 font-mono text-sm leading-relaxed overflow-x-auto" dangerouslySetInnerHTML={{ __html: highlighted }} />
      ) : (
        <pre className="overflow-x-auto p-4 bg-bg-primary text-sm font-mono text-text-primary leading-relaxed max-h-80">
          <code>{hcl}</code>
        </pre>
      )}
    </div>
  )
}
