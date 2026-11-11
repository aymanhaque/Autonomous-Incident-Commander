import { createHighlighter } from 'shiki'

export const hlPromise = createHighlighter({
  langs: ['hcl'],
  themes: ['github-light', 'github-dark'],
})

export type HL = Awaited<typeof hlPromise>

export const HCL_HIGHLIGHT_OPTS = {
  lang: 'hcl',
  themes: { light: 'github-light', dark: 'github-dark' },
  defaultColor: false,
} as const
