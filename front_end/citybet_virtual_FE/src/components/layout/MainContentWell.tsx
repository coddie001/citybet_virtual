import type { ReactNode } from 'react'

/** One continuous main column — sections separated by dividers, not floating cards. */
export function MainContentWell({ children }: { children: ReactNode }) {
  return (
    <div className="main-content-well flex flex-col divide-y divide-white/[0.06]">
      {children}
    </div>
  )
}

export function MainSection({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={`px-5 py-6 sm:px-8 sm:py-7 lg:px-10 lg:py-8 ${className}`}>
      {children}
    </section>
  )
}
