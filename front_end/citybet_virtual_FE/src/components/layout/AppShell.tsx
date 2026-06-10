import type { ReactNode } from 'react'

interface AppShellProps {
  header: ReactNode
  footer: ReactNode
  children: ReactNode
}

/** Single cohesive frame for header, body, and footer. */
export function AppShell({ header, footer, children }: AppShellProps) {
  return (
    <div className="app-shell flex min-h-screen flex-col">
      {header}
      <div className="app-shell-body flex min-h-0 flex-1 flex-col">
        {children}
      </div>
      {footer}
    </div>
  )
}
