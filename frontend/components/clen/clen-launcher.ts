'use client'

// Tiny launcher so any component (e.g. a document row) can open the account-mode
// Clen assistant and auto-send a seed message. Exactly one ClenDashboard registers.

type Handler = (seed: string) => void

let handler: Handler | null = null

export function registerClenLauncher(h: Handler): () => void {
  handler = h
  return () => {
    if (handler === h) handler = null
  }
}

/** Open the Clen assistant and auto-send `seed` as the first message. */
export function askClen(seed: string): void {
  handler?.(seed)
}
