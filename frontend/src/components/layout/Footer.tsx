/**
 * Footer Component
 *
 * Site footer with property info and useful links.
 */

import { cn } from '@/lib/utils'

export interface FooterProps {
  /** Show minimal footer (just copyright) */
  minimal?: boolean
}

export function Footer({ minimal = false }: FooterProps) {
  const currentYear = new Date().getFullYear()

  if (minimal) {
    return (
      <footer className="p-4 text-center text-xs text-gray-500 bg-gray-50 border-t border-gray-200">
        <p className="m-0">
          © {currentYear} Quesada Apartment. All rights reserved.
        </p>
      </footer>
    )
  }

  return (
    <footer className="bg-gray-800 text-gray-200 pt-12 pb-6 px-4">
      <div
        className={cn(
          'max-w-[1200px] mx-auto',
          'grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-8'
        )}
      >
        {/* Property Info */}
        <div className="min-w-0">
          <h3 className="text-xl font-bold text-white mb-3">
            ☀️ Quesada Apartment
          </h3>
          <p className="text-sm leading-relaxed text-gray-400">
            Your vacation home in the Costa Blanca region. Experience the best of
            Spanish sunshine, beaches, and culture in Quesada, Alicante.
          </p>
        </div>

        {/* Quick Links */}
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-2">
            Quick Links
          </h4>
          <ul className="list-none m-0 p-0">
            <li className="text-sm text-gray-400 mb-1.5">
              <a
                href="#availability"
                className="text-gray-400 no-underline transition-colors duration-200 hover:text-white"
              >
                Check Availability
              </a>
            </li>
            <li className="text-sm text-gray-400 mb-1.5">
              <a
                href="#property"
                className="text-gray-400 no-underline transition-colors duration-200 hover:text-white"
              >
                Property Details
              </a>
            </li>
            <li className="text-sm text-gray-400 mb-1.5">
              <a
                href="#area"
                className="text-gray-400 no-underline transition-colors duration-200 hover:text-white"
              >
                Explore the Area
              </a>
            </li>
          </ul>
        </div>

        {/* Contact */}
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-2">
            Contact
          </h4>
          <ul className="list-none m-0 p-0">
            <li className="text-sm text-gray-400 mb-1.5">
              Chat with our AI assistant 24/7
            </li>
            <li className="text-sm text-gray-400 mb-1.5">
              📍 Quesada, Alicante, Spain
            </li>
          </ul>
        </div>
      </div>

      <div
        className={cn(
          'max-w-[1200px] mx-auto mt-8 pt-6',
          'border-t border-gray-700',
          'flex flex-col sm:flex-row justify-between items-center gap-4'
        )}
      >
        <p className="m-0 text-xs text-gray-500">
          © {currentYear} Quesada Apartment. All rights reserved.
        </p>
        <div className="flex gap-6">
          <a
            href="/privacy"
            className="text-xs text-gray-500 no-underline transition-colors duration-200 hover:text-gray-400"
          >
            Privacy Policy
          </a>
          <a
            href="/terms"
            className="text-xs text-gray-500 no-underline transition-colors duration-200 hover:text-gray-400"
          >
            Terms of Service
          </a>
        </div>
      </div>
    </footer>
  )
}

export default Footer
