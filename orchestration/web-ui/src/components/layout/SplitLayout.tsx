import { useState, type ReactNode } from 'react'

const MIN_LEFT_PCT = 22
const MAX_LEFT_PCT = 40

interface Props {
  leftPane: ReactNode
  rightPane: ReactNode
  defaultLeftWidth?: number
}

export default function SplitLayout({ leftPane, rightPane, defaultLeftWidth = 30 }: Props) {
  const [leftWidth, setLeftWidth] = useState(defaultLeftWidth)
  const [collapsed, setCollapsed] = useState(false)

  function onHandleMouseDown(e: React.MouseEvent) {
    e.preventDefault()
    const startX = e.clientX
    const startW = leftWidth
    let didDrag = false

    function onMove(mv: MouseEvent) {
      if (Math.abs(mv.clientX - startX) > 4) {
        didDrag = true
        const next = ((startW / 100) * window.innerWidth + (mv.clientX - startX)) / window.innerWidth * 100
        setLeftWidth(Math.max(MIN_LEFT_PCT, Math.min(MAX_LEFT_PCT, next)))
      }
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      if (!didDrag) setCollapsed(true)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left pane */}
      <div
        className="flex-shrink-0 bg-bg-elevated overflow-y-auto transition-all duration-200"
        style={{ width: collapsed ? 0 : `${leftWidth}%`, overflow: collapsed ? 'hidden' : undefined }}
      >
        {!collapsed && leftPane}
      </div>

      {/* Full-height handle — click to collapse/expand, drag to resize */}
      <div
        className="w-1 flex-shrink-0 bg-border hover:bg-accent-500 transition-colors z-10"
        style={{ cursor: collapsed ? 'pointer' : 'col-resize' }}
        onMouseDown={collapsed ? undefined : onHandleMouseDown}
        onClick={collapsed ? () => setCollapsed(false) : undefined}
      />

      {/* Right pane */}
      <div className="flex-1 overflow-y-auto bg-bg-secondary">
        {rightPane}
      </div>
    </div>
  )
}
