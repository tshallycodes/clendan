import { dark } from '@clerk/themes'

export const clerkDarkAppearance = {
  baseTheme: dark,
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
    card: 'bg-[#111111] border border-[#2c2c2c] shadow-none',
    headerTitle: 'text-[#f0f0f0]',
    headerSubtitle: 'text-[#888888]',
    socialButtonsBlockButton: 'bg-[#1a1a1a] border border-[#2c2c2c] text-[#f0f0f0] hover:bg-[#222222]',
    socialButtonsBlockButtonText: 'text-[#f0f0f0] font-medium',
    dividerLine: 'bg-[#2c2c2c]',
    dividerText: 'text-[#555555]',
    formFieldLabel: 'text-[#a0a0a0]',
    formButtonPrimary: 'bg-[#00C853] text-black hover:bg-[#00a844]',
    footerActionText: 'text-[#666666]',
    footerActionLink: 'text-[#00C853] hover:text-[#00a844]',
  },
}
