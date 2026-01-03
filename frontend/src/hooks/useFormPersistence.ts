'use client'

/**
 * useFormPersistence Hook
 *
 * Persists form state to sessionStorage for recovery across browser refreshes.
 * Uses sessionStorage (not localStorage) so data clears when tab closes - appropriate
 * for sensitive booking data that shouldn't persist indefinitely.
 *
 * Key behaviors:
 * - Initializes from sessionStorage on mount (lazy initialization)
 * - Syncs to sessionStorage on every value change
 * - Provides clear() function for cleanup after successful submission
 * - Handles SSR safely (no window access during server render)
 *
 * Feature: 012-fix-routing-waf (T006)
 */

import { useState, useEffect, useCallback } from 'react'

interface UseFormPersistenceOptions<T> {
  /** Storage key - should be unique per form */
  key: string
  /** Initial value when nothing in storage */
  initialValue: T
  /** Custom serializer (default: JSON.stringify) */
  serialize?: (value: T) => string
  /** Custom deserializer (default: JSON.parse) */
  deserialize?: (stored: string) => T
}

/**
 * Hook for persisting form state across browser refreshes using sessionStorage.
 *
 * @example
 * ```tsx
 * const [formData, setFormData, clearFormData] = useFormPersistence({
 *   key: 'booking-form-state',
 *   initialValue: { dates: undefined, guestDetails: null, currentStep: 'dates' },
 * })
 * ```
 */
export function useFormPersistence<T>({
  key,
  initialValue,
  serialize = JSON.stringify,
  deserialize = JSON.parse,
}: UseFormPersistenceOptions<T>) {
  // Initialize from sessionStorage on mount (lazy initialization)
  // This function only runs once, preventing SSR issues
  const [value, setValue] = useState<T>(() => {
    // Guard against SSR - window/sessionStorage don't exist server-side
    if (typeof window === 'undefined') return initialValue

    const stored = sessionStorage.getItem(key)
    if (!stored) return initialValue

    try {
      return deserialize(stored)
    } catch {
      // If stored data is corrupted, fall back to initial value
      return initialValue
    }
  })

  // Sync to sessionStorage whenever value changes
  useEffect(() => {
    // Guard against SSR
    if (typeof window === 'undefined') return

    try {
      sessionStorage.setItem(key, serialize(value))
    } catch {
      // sessionStorage might be full or disabled - fail silently
      // Form still works, just won't persist
    }
  }, [key, value, serialize])

  // Clear function for cleanup after successful booking
  const clear = useCallback(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem(key)
    }
    setValue(initialValue)
  }, [key, initialValue])

  return [value, setValue, clear] as const
}

/**
 * Custom serializer for Date objects in form state.
 * Converts Date instances to ISO strings for JSON storage.
 */
export function serializeWithDates<T>(value: T): string {
  return JSON.stringify(value, (_, v) =>
    v instanceof Date ? v.toISOString() : v
  )
}

/**
 * Custom deserializer that revives ISO date strings back to Date objects.
 * Matches ISO 8601 format: YYYY-MM-DDTHH:mm:ss.sssZ
 */
export function deserializeWithDates<T>(stored: string): T {
  return JSON.parse(stored, (_, v) =>
    typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v) ? new Date(v) : v
  )
}

export default useFormPersistence
