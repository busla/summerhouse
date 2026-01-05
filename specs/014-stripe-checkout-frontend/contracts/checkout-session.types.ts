/**
 * Checkout Session Hook Types
 *
 * TypeScript interfaces for the useCheckoutSession hook
 * that manages Stripe Checkout flow state.
 *
 * Note: API types (CheckoutSessionResponse, PaymentStatusResponse, etc.)
 * are generated from the backend OpenAPI spec via @hey-api/openapi-ts.
 * This file defines frontend-specific hook state and return types.
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-002, FR-003
 * @see specs/014-stripe-checkout-frontend/data-model.md
 */

// ============================================================================
// Generated Types (from backend OpenAPI spec)
// ============================================================================

/**
 * These types will be available after running `yarn generate:api`.
 * Re-exported here for documentation purposes.
 *
 * Import from: @/lib/api-client/types.gen
 *
 * - CheckoutSessionRequest
 * - CheckoutSessionResponse
 * - PaymentStatusResponse
 * - PaymentHistoryResponse
 * - PaymentRetryRequest
 */

// ============================================================================
// Hook State Types
// ============================================================================

/**
 * State for the checkout session creation process.
 *
 * @see FR-002, FR-003, FR-021
 */
export interface CheckoutSessionState {
  /** Whether a checkout session is being created */
  isLoading: boolean;
  /** Error message if session creation failed */
  error: string | null;
  /** Whether redirect to Stripe is in progress */
  isRedirecting: boolean;
}

/**
 * State for payment status polling.
 *
 * @see FR-010
 */
export interface PaymentStatusState {
  /** Whether status is being fetched */
  isLoading: boolean;
  /** Error message if status fetch failed */
  error: string | null;
  /** Whether payment is confirmed */
  isConfirmed: boolean;
  /** Number of poll attempts */
  pollCount: number;
}

// ============================================================================
// Hook Return Types
// ============================================================================

/**
 * Result of the useCheckoutSession hook.
 *
 * @see FR-002, FR-003, FR-014
 */
export interface UseCheckoutSessionResult {
  /** Current state */
  state: CheckoutSessionState;

  /**
   * Create a new checkout session and redirect to Stripe.
   *
   * @param reservationId - Reservation ID to pay for
   * @throws Never - errors are captured in state.error
   */
  createSession: (reservationId: string) => Promise<void>;

  /**
   * Retry payment for a reservation with failed payment.
   *
   * @param reservationId - Reservation ID to retry
   * @throws Never - errors are captured in state.error
   */
  retryPayment: (reservationId: string) => Promise<void>;

  /** Reset error state */
  clearError: () => void;
}

/**
 * Result of the usePaymentStatus hook.
 *
 * @see FR-010
 */
export interface UsePaymentStatusResult {
  /** Current state */
  state: PaymentStatusState;

  /**
   * Fetch payment status for a reservation.
   *
   * @param reservationId - Reservation ID to check
   */
  fetchStatus: (reservationId: string) => Promise<void>;

  /**
   * Start polling for payment status.
   *
   * @param reservationId - Reservation ID to poll
   * @param onConfirmed - Callback when payment is confirmed
   */
  startPolling: (
    reservationId: string,
    onConfirmed?: () => void
  ) => void;

  /** Stop polling for payment status */
  stopPolling: () => void;
}

// ============================================================================
// Component Props Types
// ============================================================================

/**
 * Props for the PaymentStep component.
 *
 * @see FR-001, FR-004
 */
export interface PaymentStepProps {
  /** Reservation ID to pay for */
  reservationId: string;
  /** Total amount in EUR (for display) */
  totalAmount: number;
  /** Callback when payment is initiated (before redirect) */
  onPaymentInitiated?: () => void;
  /** Callback when payment initiation fails */
  onError?: (error: string) => void;
}

/**
 * Props for the PaymentStatus badge component.
 *
 * @see FR-015, FR-016
 */
export interface PaymentStatusBadgeProps {
  /** Current payment status */
  status: "pending" | "processing" | "paid" | "failed" | "refunded";
  /** Show amount if available */
  amount?: number;
  /** Currency code (default: EUR) */
  currency?: string;
}

/**
 * Props for the PaymentRetryButton component.
 *
 * @see FR-014, FR-020
 */
export interface PaymentRetryButtonProps {
  /** Reservation ID to retry payment for */
  reservationId: string;
  /** Current attempt count */
  attemptCount: number;
  /** Max allowed attempts */
  maxAttempts?: number;
  /** Callback when retry is clicked */
  onRetry?: () => void;
  /** Callback when max attempts reached */
  onMaxAttemptsReached?: () => void;
}

/**
 * Props for the BookingConfirmation component (enhanced).
 *
 * @see FR-007, FR-008
 */
export interface BookingConfirmationProps {
  /** Reservation ID */
  reservationId: string;
  /** Check-in date */
  checkIn: Date;
  /** Check-out date */
  checkOut: Date;
  /** Guest name */
  guestName: string;
  /** Total amount paid (EUR cents) */
  amountPaid: number;
  /** Payment status */
  paymentStatus: "pending" | "paid" | "failed";
  /** Stripe payment ID (for reference) */
  paymentId?: string;
}
