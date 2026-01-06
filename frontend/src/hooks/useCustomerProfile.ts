'use client'

/**
 * useCustomerProfile Hook (T026-T029)
 *
 * Syncs customer profile with backend after Cognito authentication.
 * Handles both new customers (POST) and returning customers (409 → GET).
 *
 * Flow:
 * 1. After OTP verification succeeds, call syncCustomerProfile()
 * 2. POST /customers/me with name/phone to create profile
 * 3. If 409 (already exists), GET /customers/me to fetch existing
 * 4. Return customer data for use in booking flow
 *
 * Requirements: US2 (Returning customer recognition)
 */

import { useState, useCallback } from 'react'
import { ensureValidIdToken } from '@/lib/auth'
import {
  createCustomerMeCustomersMePost,
  getCustomerMeCustomersMeGet,
} from '@/lib/api-client'
import type { CustomerResponse, CustomerCreate } from '@/lib/api-client'
// Ensure client is configured
import '@/lib/api-client/config'

// === Types ===

export interface CustomerProfileInput {
  /** Customer name (from auth form) */
  name: string
  /** Customer phone (from auth form) */
  phone: string
}

export interface CustomerProfileResult {
  /** Customer profile on success */
  customer?: CustomerResponse
  /** Whether this is a returning customer (existed before) */
  isReturning?: boolean
  /** Error message on failure */
  error?: string
}

export interface UseCustomerProfileReturn {
  /** Sync customer profile with backend (create or fetch) */
  syncCustomerProfile: (input: CustomerProfileInput) => Promise<CustomerProfileResult>
  /** Fetch existing customer profile (for authenticated bypass) */
  fetchCustomerProfile: () => Promise<CustomerProfileResult>
  /** Whether operation is in progress */
  isLoading: boolean
  /** Last error from operation */
  error: string | null
  /** Customer profile data */
  customer: CustomerResponse | null
  /** Whether customer is returning (existed before sync) */
  isReturning: boolean
}

// === Logging ===

const profileLogger = {
  syncStarted: (name: string) => {
    console.info('[customer-profile] sync_started', {
      name: name.slice(0, 3) + '***',
    })
  },
  created: (customerId: string) => {
    console.info('[customer-profile] created', {
      customerId: customerId.slice(0, 8) + '...',
    })
  },
  existingFound: (customerId: string) => {
    console.info('[customer-profile] existing_found', {
      customerId: customerId.slice(0, 8) + '...',
    })
  },
  fetchSuccess: (customerId: string) => {
    console.info('[customer-profile] fetch_success', {
      customerId: customerId.slice(0, 8) + '...',
    })
  },
  error: (context: string, errorMsg: string) => {
    console.warn('[customer-profile] error', { context, errorMsg })
  },
}

// === Hook ===

/**
 * Hook for syncing customer profile with backend.
 *
 * @example
 * ```tsx
 * const { syncCustomerProfile, isLoading, customer } = useCustomerProfile()
 *
 * // After OTP verification
 * const result = await syncCustomerProfile({ name, phone })
 * if (result.customer) {
 *   onComplete(result.customer.customer_id)
 * }
 * ```
 */
export function useCustomerProfile(): UseCustomerProfileReturn {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [customer, setCustomer] = useState<CustomerResponse | null>(null)
  const [isReturning, setIsReturning] = useState(false)

  /**
   * Fetch existing customer profile.
   * Used for authenticated bypass (US3) when user is already logged in.
   */
  const fetchCustomerProfile = useCallback(async (): Promise<CustomerProfileResult> => {
    setIsLoading(true)
    setError(null)

    try {
      const token = await ensureValidIdToken()
      if (!token) {
        const errorMsg = 'Authentication required'
        setError(errorMsg)
        setIsLoading(false)
        return { error: errorMsg }
      }

      const response = await getCustomerMeCustomersMeGet({
        auth: () => token,
      })

      if (response.error) {
        // 404 = customer doesn't exist yet
        if (response.response?.status === 404) {
          setIsLoading(false)
          return { error: 'Customer profile not found' }
        }
        const errorMsg = 'Failed to fetch customer profile'
        profileLogger.error('fetch', errorMsg)
        setError(errorMsg)
        setIsLoading(false)
        return { error: errorMsg }
      }

      const customerData = response.data as CustomerResponse
      setCustomer(customerData)
      setIsReturning(true)
      setIsLoading(false)
      profileLogger.fetchSuccess(customerData.customer_id)

      return { customer: customerData, isReturning: true }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Network error'
      profileLogger.error('fetch', errorMsg)
      setError(errorMsg)
      setIsLoading(false)
      return { error: errorMsg }
    }
  }, [])

  /**
   * Sync customer profile with backend.
   * Creates new profile or fetches existing (on 409 conflict).
   */
  const syncCustomerProfile = useCallback(
    async (input: CustomerProfileInput): Promise<CustomerProfileResult> => {
      setIsLoading(true)
      setError(null)
      profileLogger.syncStarted(input.name)

      try {
        const token = await ensureValidIdToken()
        if (!token) {
          const errorMsg = 'Authentication required'
          setError(errorMsg)
          setIsLoading(false)
          return { error: errorMsg }
        }

        // Prepare create payload
        const body: CustomerCreate = {
          name: input.name || undefined,
          phone: input.phone || undefined,
        }

        // Try to create customer profile
        const createResponse = await createCustomerMeCustomersMePost({
          body,
          auth: () => token,
        })

        // Check for 409 Conflict (customer already exists)
        if (createResponse.response?.status === 409) {
          // Returning customer - fetch their existing profile
          const getResponse = await getCustomerMeCustomersMeGet({
            auth: () => token,
          })

          if (getResponse.error) {
            const errorMsg = 'Failed to fetch existing customer profile'
            profileLogger.error('sync-get', errorMsg)
            setError(errorMsg)
            setIsLoading(false)
            return { error: errorMsg }
          }

          const customerData = getResponse.data as CustomerResponse
          setCustomer(customerData)
          setIsReturning(true)
          setIsLoading(false)
          profileLogger.existingFound(customerData.customer_id)

          return { customer: customerData, isReturning: true }
        }

        // Handle other errors
        if (createResponse.error) {
          const errorMsg =
            (createResponse.error as { message?: string })?.message ||
            'Failed to create customer profile'
          profileLogger.error('sync-create', errorMsg)
          setError(errorMsg)
          setIsLoading(false)
          return { error: errorMsg }
        }

        // Success - new customer created
        const customerData = createResponse.data as CustomerResponse
        setCustomer(customerData)
        setIsReturning(false)
        setIsLoading(false)
        profileLogger.created(customerData.customer_id)

        return { customer: customerData, isReturning: false }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Network error'
        profileLogger.error('sync', errorMsg)
        setError(errorMsg)
        setIsLoading(false)
        return { error: errorMsg }
      }
    },
    []
  )

  return {
    syncCustomerProfile,
    fetchCustomerProfile,
    isLoading,
    error,
    customer,
    isReturning,
  }
}

export default useCustomerProfile
