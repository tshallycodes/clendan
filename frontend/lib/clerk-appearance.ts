import type { Appearance } from '@clerk/nextjs/server'

export const clerkDarkAppearance: Appearance = {
  variables: {
    colorBackground: '#111111',
    colorText: '#f0f0f0',
    colorTextSecondary: '#a0a0a0',
    colorPrimary: '#00C853',
    colorTextOnPrimaryBackground: '#000000',
    colorInputBackground: '#1a1a1a',
    colorInputText: '#f0f0f0',
    colorNeutral: '#888888',
    borderRadius: '4px',
    fontSize: '14px',
  },
  elements: {
    card: {
      backgroundColor: '#111111',
      border: '1px solid #2c2c2c',
      boxShadow: 'none',
    },
    headerTitle: {
      color: '#f0f0f0',
    },
    headerSubtitle: {
      color: '#888888',
    },
    socialButtonsBlockButton: {
      backgroundColor: '#1a1a1a',
      border: '1px solid #2c2c2c',
      color: '#f0f0f0',
    },
    socialButtonsBlockButtonText: {
      color: '#f0f0f0',
      fontWeight: '500',
    },
    dividerLine: {
      backgroundColor: '#2c2c2c',
    },
    dividerText: {
      color: '#555555',
    },
    formFieldLabel: {
      color: '#a0a0a0',
    },
    formFieldInput: {
      backgroundColor: '#1a1a1a',
      border: '1px solid #2c2c2c',
      color: '#f0f0f0',
    },
    formFieldInputShowPasswordButton: {
      color: '#666666',
    },
    formButtonPrimary: {
      backgroundColor: '#00C853',
      color: '#000000',
    },
    footerActionText: {
      color: '#666666',
    },
    footerActionLink: {
      color: '#00C853',
    },
    identityPreviewText: {
      color: '#f0f0f0',
    },
    identityPreviewEditButtonIcon: {
      color: '#666666',
    },
    alertText: {
      color: '#f0f0f0',
    },
    formResendCodeLink: {
      color: '#00C853',
    },
  },
}
