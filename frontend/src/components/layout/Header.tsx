'use client'

/**
 * Header Component
 *
 * Displays the Quesada Apartment branding and optional user session info.
 * Used across all pages for consistent navigation.
 */

import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

export interface HeaderProps {
  /** Optional callback when logo is clicked */
  onLogoClick?: () => void
}

export function Header({ onLogoClick }: HeaderProps) {
  const { session, signOut } = useAuth()

  return (
    <header className="bg-gradient-to-br from-blue-600 to-blue-700 text-white p-4 shadow-[0_2px_8px_rgba(0,0,0,0.1)]">
      <div className="max-w-[1200px] mx-auto flex items-center justify-between gap-4">
        {/* Logo / Brand */}
        <div
          className={cn(
            'flex items-center gap-2',
            onLogoClick && 'cursor-pointer',
            'focus:outline-2 focus:outline-white focus:outline-offset-2 focus:rounded'
          )}
          onClick={onLogoClick}
          role={onLogoClick ? 'button' : undefined}
          tabIndex={onLogoClick ? 0 : undefined}
          onKeyDown={(e) => {
            if (onLogoClick && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault()
              onLogoClick()
            }
          }}
        >
          <span className="text-2xl">☀️</span>
          <span className="text-2xl font-bold tracking-tight">
            Quesada Apartment
          </span>
        </div>

        {/* Location Badge */}
        <div
          className={cn(
            'hidden sm:flex items-center gap-1',
            'text-sm opacity-90',
            'bg-white/10 py-1.5 px-3 rounded-full'
          )}
        >
          <span className="text-sm">📍</span>
          <span className="font-medium">Quesada, Alicante</span>
        </div>

        {/* User Section */}
        {session?.isAuthenticated && (
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline text-sm opacity-90">
              {session.email}
            </span>
            <button
              className={cn(
                'bg-white/15 border-none text-white',
                'py-1.5 px-3 rounded text-sm cursor-pointer',
                'transition-colors duration-200',
                'hover:bg-white/25',
                'focus:outline-2 focus:outline-white focus:outline-offset-2'
              )}
              onClick={() => signOut()}
              aria-label="Sign out"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

export default Header
