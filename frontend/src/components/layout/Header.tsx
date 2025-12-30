'use client'

/**
 * Header Component
 *
 * Displays the Quesada Apartment branding and optional user session info.
 * Used across all pages for consistent navigation.
 */

import { useAuth } from '@/lib/auth'

export interface HeaderProps {
  /** Optional callback when logo is clicked */
  onLogoClick?: () => void
}

export function Header({ onLogoClick }: HeaderProps) {
  const { session, signOut } = useAuth()

  return (
    <header className="header">
      <div className="header-content">
        {/* Logo / Brand */}
        <div
          className="header-brand"
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
          <span className="header-logo">☀️</span>
          <span className="header-title">Quesada Apartment</span>
        </div>

        {/* Location Badge */}
        <div className="header-location">
          <span className="header-location-icon">📍</span>
          <span className="header-location-text">Quesada, Alicante</span>
        </div>

        {/* User Section */}
        {session?.isAuthenticated && (
          <div className="header-user">
            <span className="header-user-email">{session.email}</span>
            <button
              className="header-signout"
              onClick={() => signOut()}
              aria-label="Sign out"
            >
              Sign out
            </button>
          </div>
        )}
      </div>

      <style jsx>{`
        .header {
          background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
          color: white;
          padding: 1rem;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .header-content {
          max-width: 1200px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
        }

        .header-brand {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          cursor: ${onLogoClick ? 'pointer' : 'default'};
        }

        .header-brand:focus {
          outline: 2px solid white;
          outline-offset: 2px;
          border-radius: 4px;
        }

        .header-logo {
          font-size: 1.5rem;
        }

        .header-title {
          font-size: 1.5rem;
          font-weight: 700;
          letter-spacing: -0.02em;
        }

        .header-location {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          font-size: 0.875rem;
          opacity: 0.9;
          background: rgba(255, 255, 255, 0.1);
          padding: 0.375rem 0.75rem;
          border-radius: 9999px;
        }

        .header-location-icon {
          font-size: 0.875rem;
        }

        .header-location-text {
          font-weight: 500;
        }

        .header-user {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .header-user-email {
          font-size: 0.875rem;
          opacity: 0.9;
        }

        .header-signout {
          background: rgba(255, 255, 255, 0.15);
          border: none;
          color: white;
          padding: 0.375rem 0.75rem;
          border-radius: 4px;
          font-size: 0.875rem;
          cursor: pointer;
          transition: background 0.2s;
        }

        .header-signout:hover {
          background: rgba(255, 255, 255, 0.25);
        }

        .header-signout:focus {
          outline: 2px solid white;
          outline-offset: 2px;
        }

        @media (max-width: 640px) {
          .header-location {
            display: none;
          }

          .header-user-email {
            display: none;
          }
        }
      `}</style>
    </header>
  )
}

export default Header
