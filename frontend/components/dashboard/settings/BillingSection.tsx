'use client'

export function BillingSection() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-xs font-body text-brand-text">Current plan</span>
        <span className="text-[11px] font-body px-2 py-0.5 rounded-sm border border-[#00a8cc]/30 bg-[rgba(0,168,204,0.08)] text-[#00a8cc]">
          Growth
        </span>
      </div>

      <p className="text-xs font-body text-brand-text">
        Need more capacity or enterprise features?
      </p>

      <a
        href="mailto:support@clendan.com"
        className="inline-flex items-center bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-body transition-colors"
      >
        Contact us
      </a>

      <p className="text-[11px] font-body text-brand-muted">
        Billing management is coming soon.
      </p>
    </div>
  )
}
