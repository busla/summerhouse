'use client';

import { useState, useCallback } from 'react';

/**
 * Photo data structure from the backend.
 */
export interface Photo {
  id: string;
  url: string;
  caption: string;
  category: string;
}

/**
 * Props for the PhotoGallery component.
 */
interface PhotoGalleryProps {
  /** Array of photos to display */
  photos: Photo[];
  /** Optional title for the gallery */
  title?: string;
  /** Number of columns in grid view (default: 3) */
  columns?: number;
  /** Whether to show captions under photos */
  showCaptions?: boolean;
}

/**
 * PhotoGallery component for displaying property photos.
 *
 * Features:
 * - Responsive grid layout
 * - Lightbox modal for full-size viewing
 * - Keyboard navigation (arrow keys, escape)
 * - Category labels
 */
export function PhotoGallery({
  photos,
  title,
  columns = 3,
  showCaptions = true,
}: PhotoGalleryProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const openLightbox = useCallback((index: number) => {
    setSelectedIndex(index);
  }, []);

  const closeLightbox = useCallback(() => {
    setSelectedIndex(null);
  }, []);

  const goToPrevious = useCallback(() => {
    if (selectedIndex !== null && selectedIndex > 0) {
      setSelectedIndex(selectedIndex - 1);
    }
  }, [selectedIndex]);

  const goToNext = useCallback(() => {
    if (selectedIndex !== null && selectedIndex < photos.length - 1) {
      setSelectedIndex(selectedIndex + 1);
    }
  }, [selectedIndex, photos.length]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (selectedIndex === null) return;

      switch (event.key) {
        case 'ArrowLeft':
          goToPrevious();
          break;
        case 'ArrowRight':
          goToNext();
          break;
        case 'Escape':
          closeLightbox();
          break;
      }
    },
    [selectedIndex, goToPrevious, goToNext, closeLightbox]
  );

  if (photos.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No photos available
      </div>
    );
  }

  const gridColsClass = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3',
    4: 'grid-cols-2 md:grid-cols-4',
  }[columns] || 'grid-cols-3';

  return (
    <div className="photo-gallery" onKeyDown={handleKeyDown} tabIndex={0}>
      {title && (
        <h3 className="text-lg font-semibold mb-4">{title}</h3>
      )}

      {/* Thumbnail Grid */}
      <div className={`grid ${gridColsClass} gap-4`}>
        {photos.map((photo, index) => (
          <div
            key={photo.id}
            className="relative group cursor-pointer overflow-hidden rounded-lg shadow-md hover:shadow-lg transition-shadow"
            onClick={() => openLightbox(index)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && openLightbox(index)}
            aria-label={`View ${photo.caption}`}
          >
            {/* Thumbnail Image */}
            <div className="aspect-[4/3] bg-gray-100">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={photo.url}
                alt={photo.caption}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                loading="lazy"
              />
            </div>

            {/* Category Badge */}
            <span className="absolute top-2 left-2 px-2 py-1 bg-black/60 text-white text-xs rounded capitalize">
              {photo.category.replace('_', ' ')}
            </span>

            {/* Caption Overlay */}
            {showCaptions && (
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-3">
                <p className="text-white text-sm truncate">{photo.caption}</p>
              </div>
            )}

            {/* Hover Overlay */}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
          </div>
        ))}
      </div>

      {/* Photo Count */}
      <p className="text-sm text-gray-500 mt-4 text-center">
        {photos.length} photo{photos.length !== 1 ? 's' : ''}
      </p>

      {/* Lightbox Modal */}
      {selectedIndex !== null && photos[selectedIndex] && (() => {
        const selectedPhoto = photos[selectedIndex];
        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/90"
            onClick={closeLightbox}
            role="dialog"
            aria-modal="true"
            aria-label="Photo lightbox"
          >
            {/* Close Button */}
            <button
              className="absolute top-4 right-4 text-white/80 hover:text-white p-2"
              onClick={closeLightbox}
              aria-label="Close lightbox"
            >
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Previous Button */}
            {selectedIndex > 0 && (
              <button
                className="absolute left-4 top-1/2 -translate-y-1/2 text-white/80 hover:text-white p-2"
                onClick={(e) => {
                  e.stopPropagation();
                  goToPrevious();
                }}
                aria-label="Previous photo"
              >
                <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            )}

            {/* Next Button */}
            {selectedIndex < photos.length - 1 && (
              <button
                className="absolute right-4 top-1/2 -translate-y-1/2 text-white/80 hover:text-white p-2"
                onClick={(e) => {
                  e.stopPropagation();
                  goToNext();
                }}
                aria-label="Next photo"
              >
                <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            )}

            {/* Full-size Image */}
            <div
              className="max-w-[90vw] max-h-[80vh] flex flex-col items-center"
              onClick={(e) => e.stopPropagation()}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={selectedPhoto.url}
                alt={selectedPhoto.caption}
                className="max-w-full max-h-[70vh] object-contain rounded-lg"
              />
              <div className="mt-4 text-center text-white">
                <p className="text-lg">{selectedPhoto.caption}</p>
                <p className="text-sm text-white/60 capitalize">
                  {selectedPhoto.category.replace('_', ' ')}
                </p>
                <p className="text-sm text-white/40 mt-2">
                  {selectedIndex + 1} / {photos.length}
                </p>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}

export default PhotoGallery;
