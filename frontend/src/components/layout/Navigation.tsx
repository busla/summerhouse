'use client'

/**
 * Navigation Component
 *
 * Main navigation bar for the Summerhouse application.
 * Combines Header with optional navigation links and mobile menu.
 */

import { useState } from 'react'
import { Header } from './Header'

export interface NavLink {
  label: string
  href: string
  active?: boolean
}

export interface NavigationProps {
  /** Navigation links to display */
  links?: NavLink[]
  /** Currently active path */
  activePath?: string
  /** Callback when a nav link is clicked */
  onNavigate?: (href: string) => void
}

export function Navigation({ links = [], activePath, onNavigate }: NavigationProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const defaultLinks: NavLink[] = [
    { label: 'Book Now', href: '/' },
    { label: 'About', href: '/about' },
    { label: 'Location', href: '/location' },
    { label: 'Pricing', href: '/pricing' },
    { label: 'Area Guide', href: '/area-guide' },
    { label: 'FAQ', href: '/faq' },
    { label: 'Contact', href: '/contact' },
  ]

  const navLinks = links.length > 0 ? links : defaultLinks

  const handleNavClick = (href: string) => {
    setMobileMenuOpen(false)
    if (onNavigate) {
      onNavigate(href)
    }
  }

  return (
    <div className="navigation">
      <Header onLogoClick={() => handleNavClick('/')} />

      {/* Desktop Navigation */}
      <nav className="nav-desktop">
        <div className="nav-content">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={`nav-link ${activePath === link.href ? 'active' : ''}`}
              onClick={(e) => {
                if (onNavigate) {
                  e.preventDefault()
                  handleNavClick(link.href)
                }
              }}
            >
              {link.label}
            </a>
          ))}
        </div>
      </nav>

      {/* Mobile Menu Toggle */}
      <button
        className="mobile-toggle"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={mobileMenuOpen}
      >
        <span className={`hamburger ${mobileMenuOpen ? 'open' : ''}`}>
          <span />
          <span />
          <span />
        </span>
      </button>

      {/* Mobile Navigation */}
      {mobileMenuOpen && (
        <nav className="nav-mobile">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={`nav-link ${activePath === link.href ? 'active' : ''}`}
              onClick={(e) => {
                if (onNavigate) {
                  e.preventDefault()
                }
                handleNavClick(link.href)
              }}
            >
              {link.label}
            </a>
          ))}
        </nav>
      )}

      <style jsx>{`
        .navigation {
          position: relative;
        }

        .nav-desktop {
          background: white;
          border-bottom: 1px solid #e5e7eb;
          display: none;
        }

        @media (min-width: 768px) {
          .nav-desktop {
            display: block;
          }
        }

        .nav-content {
          max-width: 1200px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0 1rem;
        }

        .nav-link {
          display: block;
          padding: 0.75rem 1rem;
          color: #4b5563;
          text-decoration: none;
          font-size: 0.875rem;
          font-weight: 500;
          transition: color 0.2s, background 0.2s;
          border-radius: 4px;
        }

        .nav-link:hover {
          color: #1d4ed8;
          background: #eff6ff;
        }

        .nav-link.active {
          color: #1d4ed8;
          background: #eff6ff;
        }

        .mobile-toggle {
          position: fixed;
          bottom: 1rem;
          right: 1rem;
          width: 48px;
          height: 48px;
          border-radius: 50%;
          background: #1d4ed8;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 12px rgba(29, 78, 216, 0.3);
          z-index: 100;
        }

        @media (min-width: 768px) {
          .mobile-toggle {
            display: none;
          }
        }

        .hamburger {
          display: flex;
          flex-direction: column;
          gap: 4px;
          width: 20px;
        }

        .hamburger span {
          display: block;
          height: 2px;
          background: white;
          border-radius: 1px;
          transition: transform 0.3s, opacity 0.3s;
        }

        .hamburger.open span:nth-child(1) {
          transform: rotate(45deg) translate(4px, 4px);
        }

        .hamburger.open span:nth-child(2) {
          opacity: 0;
        }

        .hamburger.open span:nth-child(3) {
          transform: rotate(-45deg) translate(4px, -4px);
        }

        .nav-mobile {
          position: fixed;
          bottom: 72px;
          right: 1rem;
          background: white;
          border-radius: 12px;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
          overflow: hidden;
          z-index: 99;
          min-width: 160px;
        }

        .nav-mobile .nav-link {
          padding: 0.875rem 1.25rem;
          border-bottom: 1px solid #f3f4f6;
        }

        .nav-mobile .nav-link:last-child {
          border-bottom: none;
        }

        @media (min-width: 768px) {
          .nav-mobile {
            display: none;
          }
        }
      `}</style>
    </div>
  )
}

export default Navigation
