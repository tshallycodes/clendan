'use client'

import { useState } from 'react'
import { StepProgress } from './_components/StepProgress'
import { Step1 } from './_components/Step1'
import { Step2 } from './_components/Step2'
import { Step3 } from './_components/Step3'
import { Step4 } from './_components/Step4'

const TOTAL_STEPS = 4

export default function OnboardingPage() {
  const [step, setStep] = useState(1)

  function next() {
    setStep((s) => Math.min(s + 1, TOTAL_STEPS))
  }

  function back() {
    setStep((s) => Math.max(s - 1, 1))
  }

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col items-center justify-center p-6">
      {step > 1 && (
        <div className="fixed top-0 left-0 right-0 flex items-center px-6 py-4">
          <button
            type="button"
            onClick={back}
            className="text-xs font-mono text-brand-muted hover:text-brand-text transition-colors"
          >
            ← Back
          </button>
        </div>
      )}

      <div className="w-full max-w-md">
        <div className="flex flex-col items-center gap-3 mb-10">
          <span className="w-10 h-10 rounded-sm border border-brand-green flex items-center justify-center font-heading font-bold text-brand-green text-lg">
            C
          </span>
          <span className="font-heading font-bold text-brand-text text-xs tracking-[0.15em] uppercase">
            Clendan
          </span>
        </div>

        <StepProgress current={step} total={TOTAL_STEPS} />

        {step === 1 && <Step1 onNext={next} />}
        {step === 2 && <Step2 onNext={next} onSkip={next} />}
        {step === 3 && <Step3 onNext={next} onSkip={next} />}
        {step === 4 && <Step4 onBack={back} />}
      </div>
    </div>
  )
}
