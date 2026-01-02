/**
 * QuickLinks Component
 *
 * Card-based navigation to key sections: Gallery, Location, Book, Agent.
 * Provides quick access to the main user journeys.
 *
 * Requirements: FR-003 - Homepage MUST include prominent booking call-to-action
 */

import Link from 'next/link'
import {
  Images,
  MapPin,
  Calendar,
  MessageCircle,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface QuickLink {
  icon: LucideIcon
  title: string
  description: string
  href: string
  accent?: boolean
}

export interface QuickLinksProps {
  /** Custom class name */
  className?: string
}

const quickLinks: QuickLink[] = [
  {
    icon: Calendar,
    title: 'Book Your Stay',
    description: 'Check availability and reserve your dates',
    href: '/book',
    accent: true,
  },
  {
    icon: Images,
    title: 'View Gallery',
    description: 'Explore photos of the apartment and amenities',
    href: '/gallery',
  },
  {
    icon: MapPin,
    title: 'Location & Area',
    description: 'Discover nearby beaches, golf, and attractions',
    href: '/location',
  },
  {
    icon: MessageCircle,
    title: 'Chat with Agent',
    description: 'Get instant answers from our AI assistant',
    href: '/agent',
  },
]

export function QuickLinks({ className }: QuickLinksProps) {
  return (
    <section
      className={cn('py-16 md:py-20 px-4 md:px-8 bg-white', className)}
      aria-labelledby="quicklinks-heading"
    >
      <div className="max-w-[1200px] mx-auto">
        <h2
          id="quicklinks-heading"
          className="text-center text-[1.75rem] md:text-[2rem] font-bold text-gray-900 mb-2"
        >
          Plan Your Perfect Stay
        </h2>
        <p className="text-center text-base md:text-lg text-gray-500 mb-10 md:mb-12">
          Everything you need to book your vacation
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5 lg:gap-6">
          {quickLinks.map(({ icon: Icon, title, description, href, accent }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                'group relative flex flex-col p-6 rounded-2xl',
                'transition-all duration-200 border border-transparent',
                accent
                  ? 'bg-blue-700 text-white hover:bg-blue-800'
                  : [
                      'bg-gray-50',
                      'hover:bg-white hover:border-gray-200',
                      'hover:shadow-[0_8px_24px_rgba(0,0,0,0.08)]',
                      'hover:-translate-y-1',
                    ]
              )}
            >
              <div
                className={cn(
                  'flex items-center justify-center',
                  'w-14 h-14 mb-4 rounded-xl',
                  'shadow-[0_2px_8px_rgba(0,0,0,0.06)]',
                  accent
                    ? 'bg-white/20 text-white shadow-none'
                    : 'bg-white text-blue-700'
                )}
              >
                <Icon size={28} strokeWidth={1.5} aria-hidden="true" />
              </div>
              <h3
                className={cn(
                  'text-lg font-semibold mb-1.5',
                  accent ? 'text-white' : 'text-gray-900'
                )}
              >
                {title}
              </h3>
              <p
                className={cn(
                  'text-sm leading-relaxed grow',
                  accent ? 'text-white/85' : 'text-gray-500'
                )}
              >
                {description}
              </p>
              <span
                className={cn(
                  'absolute top-6 right-6 text-xl',
                  'transition-all duration-200',
                  accent
                    ? 'text-white/60 group-hover:text-white group-hover:translate-x-1'
                    : 'text-gray-400 group-hover:text-blue-700 group-hover:translate-x-1'
                )}
                aria-hidden="true"
              >
                &rarr;
              </span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}

export default QuickLinks
