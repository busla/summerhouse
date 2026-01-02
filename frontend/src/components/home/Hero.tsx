/**
 * Hero Component
 *
 * Full-width hero section for the homepage with background image,
 * property tagline, and call-to-action button.
 *
 * Requirements: FR-001 - Homepage MUST display hero imagery
 */

import Link from 'next/link'
import { cn } from '@/lib/utils'

export interface HeroProps {
  /** Main headline text */
  title: string
  /** Subtitle or tagline */
  subtitle: string
  /** Background image URL */
  backgroundImage?: string
  /** Call-to-action button text */
  ctaText: string
  /** Call-to-action link destination */
  ctaHref: string
  /** Secondary CTA text (optional) */
  secondaryCtaText?: string
  /** Secondary CTA link (optional) */
  secondaryCtaHref?: string
}

export function Hero({
  title,
  subtitle,
  backgroundImage = '/images/hero-pool.jpg',
  ctaText,
  ctaHref,
  secondaryCtaText,
  secondaryCtaHref,
}: HeroProps) {
  return (
    <section
      className="relative min-h-[70vh] md:min-h-[80vh] flex items-center justify-center px-4 py-8 md:px-8 md:py-12"
      aria-label="Hero section"
    >
      {/* Background with overlay */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{
          backgroundImage: `url(${backgroundImage})`,
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-black/30 to-black/50" />
      </div>

      {/* Content */}
      <div className="relative z-10 max-w-[800px] text-center text-white">
        <h1
          className={cn(
            'text-[2.5rem] md:text-[3.5rem] lg:text-[4rem]',
            'font-bold leading-tight mb-4',
            '[text-shadow:0_2px_8px_rgba(0,0,0,0.3)]'
          )}
        >
          {title}
        </h1>
        <p
          className={cn(
            'text-lg md:text-xl leading-relaxed mb-8',
            'opacity-95 max-w-[600px] mx-auto',
            '[text-shadow:0_1px_4px_rgba(0,0,0,0.2)]'
          )}
        >
          {subtitle}
        </p>

        <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
          <Link
            href={ctaHref}
            className={cn(
              'inline-flex items-center justify-center',
              'py-3.5 px-8 text-base font-semibold',
              'bg-blue-700 text-white rounded-lg',
              'shadow-[0_4px_12px_rgba(29,78,216,0.4)]',
              'transition-all duration-200 min-w-[180px]',
              'hover:bg-blue-800 hover:-translate-y-0.5',
              'hover:shadow-[0_6px_16px_rgba(29,78,216,0.5)]'
            )}
          >
            {ctaText}
          </Link>
          {secondaryCtaText && secondaryCtaHref && (
            <Link
              href={secondaryCtaHref}
              className={cn(
                'inline-flex items-center justify-center',
                'py-3.5 px-8 text-base font-semibold',
                'bg-white/15 text-white rounded-lg',
                'border-2 border-white/50 backdrop-blur-sm',
                'transition-all duration-200 min-w-[180px]',
                'hover:bg-white/25 hover:border-white/70'
              )}
            >
              {secondaryCtaText}
            </Link>
          )}
        </div>
      </div>
    </section>
  )
}

export default Hero
