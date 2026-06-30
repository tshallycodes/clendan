'use client'

import { motion } from 'framer-motion'
import { useClen } from './useClen'
import { ClenPanel } from './ClenPanel'

export function ClenButton() {
  const { isOpen, setIsOpen } = useClen('docs')

  return (
    <>
      <motion.button
        onClick={() => setIsOpen(prev => !prev)}
        aria-label={isOpen ? 'Close Clen assistant' : 'Open Clen assistant'}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className="fixed bottom-6 right-6 z-50 w-[52px] h-[52px] rounded-full flex items-center justify-center shadow-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-[#00C853]"
        style={{ background: '#00C853' }}
      >
        <span
          className="text-black font-body font-bold text-lg leading-none"
          aria-hidden="true"
        >
          C
        </span>
      </motion.button>

      <ClenPanel
        mode="docs"
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        position="floating"
      />
    </>
  )
}
