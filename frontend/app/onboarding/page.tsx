'use client'

import { useState } from 'react'
import { Logo } from '@/components/Logo'
import { StepProgress } from './_components/StepProgress'
import { StepName } from './_components/StepName'
import { Step1 } from './_components/Step1'
import { Step2 } from './_components/Step2'
import { Step3 } from './_components/Step3'
import { Step4 } from './_components/Step4'

const TOTAL_STEPS = 5

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
        <div className="flex justify-center mb-10">
          <Logo size="lg" href={null} />
        </div>

        <StepProgress current={step} total={TOTAL_STEPS} />

        {step === 1 && <StepName onNext={next} />}
        {step === 2 && <Step1 onNext={next} />}
        {step === 3 && <Step2 onNext={next} onSkip={next} />}
        {step === 4 && <Step3 onNext={next} onSkip={next} />}
        {step === 5 && <Step4 onBack={back} />}
      </div>
    </div>
  )
}
