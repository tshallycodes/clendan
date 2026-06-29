'use client'

import { SignIn, SignUp } from '@clerk/nextjs'
import { clerkDarkAppearance, clerkLightAppearance } from '@/lib/clerk-appearance'
import { useState } from 'react'

function getAppearance() {
  try {
    return (localStorage.getItem('theme') ?? 'dark') === 'dark'
      ? clerkDarkAppearance
      : clerkLightAppearance
  } catch {
    return clerkDarkAppearance
  }
}

export function AuthSignIn() {
  const [appearance] = useState(getAppearance)
  return <SignIn appearance={appearance} />
}

export function AuthSignUp() {
  const [appearance] = useState(getAppearance)
  return <SignUp appearance={appearance} />
}
