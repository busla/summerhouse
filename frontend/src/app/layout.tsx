import type { Metadata, Viewport } from 'next'
import './globals.css'
import 'leaflet/dist/leaflet.css'
import 'react-day-picker/style.css'
import { Navigation } from '@/components/layout/Navigation'
import { ChatWidget } from '@/components/layout/ChatWidget'
import { AmplifyProvider } from '@/components/providers/AmplifyProvider'

export const metadata: Metadata = {
  title: 'Quesada Apartment - Vacation Rental in Costa Blanca',
  description:
    'Book your stay at our beautiful apartment in Quesada, Alicante. Chat with our AI assistant to check availability, get pricing, and complete your booking.',
  keywords: [
    'vacation rental',
    'Quesada',
    'Alicante',
    'Costa Blanca',
    'Spain',
    'holiday apartment',
    'beach house',
  ],
  authors: [{ name: 'Quesada Apartment' }],
  openGraph: {
    title: 'Quesada Apartment - Vacation Rental in Costa Blanca',
    description:
      'Book your stay at our beautiful apartment in Quesada, Alicante. Chat with our AI assistant.',
    type: 'website',
    locale: 'en_US',
    alternateLocale: 'es_ES',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#1d4ed8',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>
        <AmplifyProvider>
          <Navigation />
          <main className="app-container">{children}</main>
          <ChatWidget />
        </AmplifyProvider>
      </body>
    </html>
  )
}
