/**
 * Homepage - Property Discovery
 *
 * Main landing page for the Quesada Apartment vacation rental.
 * Showcases the property with hero imagery, highlights, and quick navigation.
 *
 * Requirements:
 * - FR-001: Homepage MUST display hero imagery
 * - FR-002: Homepage MUST display key property highlights
 * - FR-003: Homepage MUST include prominent booking call-to-action
 */

import type { Metadata } from 'next'
import { Footer } from '@/components/layout/Footer'
import { Hero } from '@/components/home/Hero'
import { PropertyHighlights } from '@/components/home/PropertyHighlights'
import { QuickLinks } from '@/components/home/QuickLinks'

export const metadata: Metadata = {
  title: 'Quesada Apartment | Your Costa Blanca Vacation Home',
  description:
    'Book your perfect getaway at our sunny 2-bedroom apartment in Quesada, Alicante. Shared pool, free WiFi, and just minutes from beautiful beaches.',
  openGraph: {
    title: 'Quesada Apartment | Your Costa Blanca Vacation Home',
    description:
      'Book your perfect getaway at our sunny 2-bedroom apartment in Quesada, Alicante. Shared pool, free WiFi, and just minutes from beautiful beaches.',
    type: 'website',
  },
}

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Main Content */}
      <main className="flex-1">
        {/* Hero Section */}
        <Hero
          title="Your Costa Blanca Escape"
          subtitle="Experience the perfect blend of Spanish sunshine, relaxation, and adventure at our beautiful Quesada apartment."
          backgroundImage="/images/hero-pool.jpg"
          ctaText="Book Your Stay"
          ctaHref="/book"
          secondaryCtaText="Chat with Agent"
          secondaryCtaHref="/agent"
        />

        {/* Property Features */}
        <PropertyHighlights />

        {/* Quick Navigation */}
        <QuickLinks />
      </main>

      {/* Footer */}
      <Footer />
    </div>
  )
}
