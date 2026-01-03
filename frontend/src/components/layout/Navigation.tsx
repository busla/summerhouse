'use client'

/**
 * Navigation Component
 *
 * Main navigation bar for the Quesada Apartment booking application.
 * Combines Header with optional navigation links and mobile menu.
 * Auto-detects active path using Next.js usePathname().
 */

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { Header } from './Header'
import { cn } from '@/lib/utils'

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
  const pathname = usePathname()

  // Use provided activePath or auto-detect from pathname
  const currentPath = activePath ?? pathname

  // Normalize pathname for comparison (T017)
  // Removes trailing slash except for root path '/'
  // This ensures /gallery matches /gallery/ for active state
  const normalizePathname = (path: string): string =>
    path === '/' ? path : path.replace(/\/$/, '')

  // Check if a link is active using normalized paths (T018)
  const isActive = (href: string): boolean =>
    normalizePathname(currentPath) === normalizePathname(href)

  // Use trailing slashes to match Next.js trailingSlash: true config
  // This ensures URLs match the static export structure (/gallery/index.html)
  const defaultLinks: NavLink[] = [
    { label: 'Home', href: '/' },
    { label: 'Gallery', href: '/gallery/' },
    { label: 'Location', href: '/location/' },
    { label: 'Book', href: '/book/' },
    { label: 'Agent', href: '/agent/' },
  ]

  const navLinks = links.length > 0 ? links : defaultLinks

  const handleNavClick = (href: string) => {
    setMobileMenuOpen(false)
    if (onNavigate) {
      onNavigate(href)
    }
  }

  return (
    <div className="relative">
      <Header onLogoClick={() => handleNavClick('/')} />

      {/* Desktop Navigation */}
      <nav className="hidden md:block bg-white border-b border-gray-200">
        <div className="max-w-[1200px] mx-auto flex items-center gap-2 px-4">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={cn(
                'block py-3 px-4 text-sm font-medium rounded',
                'text-gray-600 no-underline',
                'transition-colors duration-200',
                'hover:text-blue-700 hover:bg-blue-50',
                isActive(link.href) && 'text-blue-700 bg-blue-50'
              )}
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
        className={cn(
          'fixed md:hidden bottom-4 right-4',
          'w-12 h-12 rounded-full',
          'bg-blue-700 border-none cursor-pointer',
          'flex items-center justify-center',
          'shadow-[0_4px_12px_rgba(29,78,216,0.3)]',
          'z-[100]'
        )}
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={mobileMenuOpen}
      >
        <span className="flex flex-col gap-1 w-5">
          <span
            className={cn(
              'block h-0.5 bg-white rounded-sm transition-all duration-300',
              mobileMenuOpen && 'rotate-45 translate-y-1.5'
            )}
          />
          <span
            className={cn(
              'block h-0.5 bg-white rounded-sm transition-all duration-300',
              mobileMenuOpen && 'opacity-0'
            )}
          />
          <span
            className={cn(
              'block h-0.5 bg-white rounded-sm transition-all duration-300',
              mobileMenuOpen && '-rotate-45 -translate-y-1.5'
            )}
          />
        </span>
      </button>

      {/* Mobile Navigation */}
      {mobileMenuOpen && (
        <nav
          className={cn(
            'fixed md:hidden bottom-[72px] right-4',
            'bg-white rounded-xl min-w-[160px]',
            'shadow-[0_4px_20px_rgba(0,0,0,0.15)]',
            'overflow-hidden z-[99]'
          )}
        >
          {navLinks.map((link, index) => (
            <a
              key={link.href}
              href={link.href}
              className={cn(
                'block py-3.5 px-5 text-sm font-medium',
                'text-gray-600 no-underline',
                'transition-colors duration-200',
                'hover:text-blue-700 hover:bg-blue-50',
                isActive(link.href) && 'text-blue-700 bg-blue-50',
                index < navLinks.length - 1 && 'border-b border-gray-100'
              )}
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
    </div>
  )
}

export default Navigation
