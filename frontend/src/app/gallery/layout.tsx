import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Photo Gallery | Quesada Apartment',
  description:
    'Browse photos of our beautiful vacation rental apartment in Ciudad Quesada, Costa Blanca. See the living room, bedrooms, kitchen, terrace, and stunning views.',
  openGraph: {
    title: 'Photo Gallery | Quesada Apartment',
    description:
      'Browse photos of our beautiful vacation rental apartment in Ciudad Quesada, Costa Blanca.',
    type: 'website',
  },
}

export default function GalleryLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}
