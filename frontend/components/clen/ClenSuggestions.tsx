'use client'

import { motion } from 'framer-motion'

interface Props {
  onSelect: (text: string) => void
}

const SUGGESTIONS = [
  'How does invoice processing work?',
  'What integrations do you support?',
  'How much does Clendan cost?',
  "What's the Invoice Parser API?",
]

export function ClenSuggestions({ onSelect }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="px-4 pb-4"
    >
      <p className="text-[11px] font-body text-brand-muted uppercase tracking-wider mb-3">
        Suggestions
      </p>
      <div className="grid grid-cols-2 gap-2">
        {SUGGESTIONS.map((text, i) => (
          <motion.button
            key={text}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15, delay: i * 0.04 }}
            onClick={() => onSelect(text)}
            className="border border-brand-border bg-transparent text-[11px] font-body text-brand-secondary px-3 py-2 rounded-sm hover:border-brand-green/30 hover:text-brand-text transition-colors text-left leading-snug"
          >
            {text}
          </motion.button>
        ))}
      </div>
    </motion.div>
  )
}
