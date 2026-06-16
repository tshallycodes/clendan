'use client'

import { motion } from 'framer-motion'

interface Props {
  autoApproved: number
  total: number
}

const TIERS = [
  { min: 90, label: 'Fully Automated', color: '#00C853' },
  { min: 80, label: 'High Efficiency',  color: '#00C853' },
  { min: 60, label: 'Automating',       color: '#f5a623' },
  { min: 0,  label: 'Getting Started',  color: '#00a8cc' },
]

function getTier(rate: number) {
  return TIERS.find((t) => rate >= t.min) ?? TIERS[TIERS.length - 1]
}

export function AutomationRing({ autoApproved, total }: Props) {
  const rate = total > 0 ? Math.round((autoApproved / total) * 100) : 0
  const radius = 34
  const circumference = 2 * Math.PI * radius
  const strokeDash = (rate / 100) * circumference
  const tier = getTier(rate)

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4 flex items-center gap-6">
      {/* Ring */}
      <div className="relative w-20 h-20 shrink-0">
        <svg viewBox="0 0 84 84" className="w-full h-full -rotate-90">
          <circle
            cx="42" cy="42" r={radius}
            fill="none" stroke="currentColor" strokeWidth="5"
            className="text-brand-border"
          />
          <motion.circle
            cx="42" cy="42" r={radius}
            fill="none"
            stroke={tier.color}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference - strokeDash }}
            transition={{ duration: 1.4, ease: [0.25, 0.46, 0.45, 0.94], delay: 0.3 }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span
            className="font-heading font-bold text-lg leading-none"
            style={{ color: tier.color }}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.5, duration: 0.3 }}
          >
            {rate}%
          </motion.span>
        </div>
      </div>

      {/* Text */}
      <div className="flex-1 space-y-2 min-w-0">
        <div className="space-y-0.5">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">
            Automation Rate
          </p>
          <p className="text-sm font-heading font-bold text-brand-text">
            {autoApproved} auto-executed
          </p>
          <p className="text-[10px] font-mono text-brand-muted">of {total} total runs</p>
        </div>

        {/* Tier badge */}
        <motion.div
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.7, duration: 0.3 }}
          className="flex items-center gap-2"
        >
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded-sm border"
            style={{
              color: tier.color,
              borderColor: `${tier.color}33`,
              backgroundColor: `${tier.color}10`,
            }}
          >
            {tier.label}
          </span>
          {rate >= 90 && (
            <motion.span
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 1.2, type: 'spring', stiffness: 300 }}
              className="text-[10px] font-mono text-[#00C853]"
            >
              ✓ Target exceeded
            </motion.span>
          )}
        </motion.div>

        {/* Progress to 90% target */}
        {total > 0 && rate < 90 && (
          <div>
            <div className="flex justify-between mb-1">
              <span className="text-[10px] font-mono text-brand-muted">Target: 90%</span>
              <span className="text-[10px] font-mono" style={{ color: tier.color }}>
                {90 - rate}% to go
              </span>
            </div>
            <div className="h-0.5 bg-brand-border rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: tier.color }}
                initial={{ width: 0 }}
                animate={{ width: `${Math.min((rate / 90) * 100, 100)}%` }}
                transition={{ duration: 1.4, ease: [0.25, 0.46, 0.45, 0.94], delay: 0.3 }}
              />
            </div>
          </div>
        )}

        {total === 0 && (
          <p className="text-[10px] font-mono text-brand-muted">
            Deploy a tool to start tracking
          </p>
        )}
      </div>
    </div>
  )
}
