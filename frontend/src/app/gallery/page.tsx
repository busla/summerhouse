'use client'

/**
 * Gallery Page
 *
 * Displays property photos in an organized gallery format with lightbox support.
 *
 * Requirements:
 * - FR-015: Display property photos in organized gallery format
 * - FR-016: Gallery MUST support full-screen/lightbox viewing mode
 * - FR-017: Lightbox MUST support keyboard navigation
 * - FR-018: Lightbox MUST support touch gestures on mobile
 * - FR-019: Images MUST include descriptive captions/alt text
 */

import { useState } from 'react'
import Image from 'next/image'
import Lightbox from 'yet-another-react-lightbox'
import Thumbnails from 'yet-another-react-lightbox/plugins/thumbnails'
import Zoom from 'yet-another-react-lightbox/plugins/zoom'
import 'yet-another-react-lightbox/styles.css'
import 'yet-another-react-lightbox/plugins/thumbnails.css'

import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

// Photo data with captions for accessibility (FR-019)
const photos = [
  {
    src: '/photos/01.jpg',
    alt: 'Living room with comfortable seating and natural light',
    title: 'Spacious Living Room',
    description: 'Relax in our bright, airy living space with comfortable seating',
  },
  {
    src: '/photos/02.jpg',
    alt: 'Modern kitchen with full amenities',
    title: 'Fully Equipped Kitchen',
    description: 'Cook your favorite meals in our well-appointed kitchen',
  },
  {
    src: '/photos/03.jpg',
    alt: 'Cozy bedroom with quality linens',
    title: 'Master Bedroom',
    description: 'Rest peacefully in our comfortable bedroom with quality linens',
  },
  {
    src: '/photos/04.jpg',
    alt: 'Private terrace with outdoor seating',
    title: 'Private Terrace',
    description: 'Enjoy the Costa Blanca sunshine on your private terrace',
  },
  {
    src: '/photos/05.jpg',
    alt: 'Clean bathroom with modern fixtures',
    title: 'Modern Bathroom',
    description: 'Fresh, clean bathroom with modern amenities',
  },
  {
    src: '/photos/06.jpg',
    alt: 'Beautiful view from the apartment',
    title: 'Stunning Views',
    description: 'Wake up to beautiful views of the surrounding area',
  },
]

// Convert to lightbox format
const lightboxSlides = photos.map((photo) => ({
  src: photo.src,
  alt: photo.alt,
  title: photo.title,
}))

export default function GalleryPage() {
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const [lightboxIndex, setLightboxIndex] = useState(0)

  const openLightbox = (index: number) => {
    setLightboxIndex(index)
    setLightboxOpen(true)
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Page Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Photo Gallery</h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Take a virtual tour of our beautiful Quesada apartment. Click any image
          to view in full screen.
        </p>
      </div>

      {/* Photo Grid - FR-015: Organized gallery format */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {photos.map((photo, index) => (
          <Card
            key={photo.src}
            className="overflow-hidden group cursor-pointer transition-all duration-300 hover:shadow-lg hover:-translate-y-1"
            onClick={() => openLightbox(index)}
          >
            <CardContent className="p-0">
              {/* Image Container */}
              <div className="relative aspect-[4/3] overflow-hidden">
                <Image
                  src={photo.src}
                  alt={photo.alt}
                  fill
                  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
                  className="object-cover transition-transform duration-300 group-hover:scale-105"
                />
                {/* Hover Overlay */}
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-300 flex items-center justify-center">
                  <span className="text-white opacity-0 group-hover:opacity-100 transition-opacity duration-300 font-medium">
                    View Full Size
                  </span>
                </div>
              </div>
              {/* Caption - FR-019: Descriptive captions */}
              <div className="p-4">
                <h3 className="font-semibold text-gray-900">{photo.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{photo.description}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* View All Button */}
      <div className="text-center mt-8">
        <Button
          variant="outline"
          size="lg"
          onClick={() => openLightbox(0)}
          className="gap-2"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M15 3h6v6" />
            <path d="M9 21H3v-6" />
            <path d="M21 3l-7 7" />
            <path d="M3 21l7-7" />
          </svg>
          View Slideshow
        </Button>
      </div>

      {/* Lightbox - FR-016: Full-screen viewing mode */}
      {/* FR-017: Keyboard navigation (built-in) */}
      {/* FR-018: Touch gestures (built-in) */}
      <Lightbox
        open={lightboxOpen}
        close={() => setLightboxOpen(false)}
        index={lightboxIndex}
        slides={lightboxSlides}
        plugins={[Thumbnails, Zoom]}
        thumbnails={{
          position: 'bottom',
          width: 100,
          height: 75,
          border: 2,
          borderRadius: 4,
          padding: 4,
          gap: 8,
        }}
        zoom={{
          maxZoomPixelRatio: 3,
          scrollToZoom: true,
        }}
        carousel={{
          finite: false,
          preload: 2,
        }}
        animation={{
          fade: 250,
          swipe: 300,
        }}
        controller={{
          closeOnBackdropClick: true,
        }}
        styles={{
          container: { backgroundColor: 'rgba(0, 0, 0, 0.95)' },
        }}
      />
    </div>
  )
}
