interface Props {
  alertName: string
}

export default function HighRiskBlock({ alertName }: Props) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="rounded-lg border-2 border-danger-500 bg-danger-50 p-5 flex flex-col items-center text-center gap-3"
    >
      {/* Stop icon */}
      <div className="w-12 h-12 rounded-full bg-danger-500 flex items-center justify-center">
        <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
            d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
        </svg>
      </div>

      <div>
        <p className="text-base font-semibold text-danger-600">HIGH RISK — MANUAL SIGN-OFF REQUIRED</p>
        <p className="text-sm text-danger-600/80 mt-1">
          <strong>{alertName}</strong> plan affects critical cluster infrastructure and will never auto-apply.
        </p>
      </div>

      <p className="text-xs text-danger-600/70 max-w-xs">
        Review the Terraform plan and remediation summary carefully — this is the only risk tier where a
        human must explicitly approve or deny below before anything runs.
      </p>
    </div>
  )
}
