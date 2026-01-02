/**
 * PropertyHighlights Component
 *
 * Displays key property amenities and features in a grid layout.
 * Icons use Lucide React for consistency with the design system.
 *
 * Requirements: FR-002 - Homepage MUST display key property highlights
 */

import {
  Bed,
  Bath,
  Users,
  Waves,
  Wifi,
  Car,
  Wind,
  Utensils,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface Highlight {
  icon: LucideIcon
  label: string
  value: string
}

export interface PropertyHighlightsProps {
  /** Custom class name */
  className?: string
}

/**
 * Default property highlights for the Quesada apartment.
 * These match the property specifications (max 4 guests, 2 bedrooms, etc.)
 */
const defaultHighlights: Highlight[] = [
  { icon: Bed, label: 'Bedrooms', value: '2' },
  { icon: Bath, label: 'Bathroom', value: '1' },
  { icon: Users, label: 'Max Guests', value: '4' },
  { icon: Waves, label: 'Shared Pool', value: 'Yes' },
  { icon: Wind, label: 'Air Conditioning', value: 'Yes' },
  { icon: Wifi, label: 'Free WiFi', value: 'Yes' },
  { icon: Car, label: 'Free Parking', value: 'Yes' },
  { icon: Utensils, label: 'Full Kitchen', value: 'Yes' },
]

export function PropertyHighlights({ className }: PropertyHighlightsProps) {
  return (
    <section
      className={cn('py-16 md:py-20 px-4 md:px-8 bg-gray-50', className)}
      aria-labelledby="highlights-heading"
    >
      <div className="max-w-[1200px] mx-auto">
        <h2
          id="highlights-heading"
          className="text-center text-[1.75rem] md:text-[2rem] font-bold text-gray-900 mb-2"
        >
          Property Features
        </h2>
        <p className="text-center text-base md:text-lg text-gray-500 mb-10 md:mb-12">
          Everything you need for a perfect Costa Blanca getaway
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-5 lg:gap-6">
          {defaultHighlights.map(({ icon: Icon, label, value }) => (
            <div
              key={label}
              className={cn(
                'flex items-center gap-3 p-4',
                'bg-white rounded-xl',
                'shadow-[0_1px_3px_rgba(0,0,0,0.05)]',
                'transition-all duration-200',
                'hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(0,0,0,0.08)]'
              )}
            >
              <div
                className={cn(
                  'flex items-center justify-center',
                  'w-12 h-12 shrink-0',
                  'bg-blue-50 rounded-[10px] text-blue-700'
                )}
              >
                <Icon size={24} strokeWidth={1.5} aria-hidden="true" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-lg font-semibold text-gray-900 leading-tight">
                  {value}
                </span>
                <span className="text-[0.8125rem] text-gray-500 whitespace-nowrap overflow-hidden text-ellipsis">
                  {label}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default PropertyHighlights
