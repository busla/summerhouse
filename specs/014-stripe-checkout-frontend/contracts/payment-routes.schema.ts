/**
 * Payment Route Contracts
 *
 * TypeScript schemas and types for payment-related routes.
 * These define the expected props, search params, and return URLs
 * for the Stripe Checkout integration.
 *
 * @see specs/014-stripe-checkout-frontend/spec.md
 * @see specs/014-stripe-checkout-frontend/data-model.md
 */

import { z } from "zod";

// ============================================================================
// Constants
// ============================================================================

/** Maximum allowed payment attempts before requiring support contact */
export const MAX_PAYMENT_ATTEMPTS = 3;

/** Stripe Checkout session validity in minutes */
export const CHECKOUT_SESSION_EXPIRY_MINUTES = 30;

/** Polling interval for payment status verification (ms) */
export const PAYMENT_STATUS_POLL_INTERVAL = 2000;

/** Maximum polling duration before showing fallback message (ms) */
export const PAYMENT_STATUS_POLL_TIMEOUT = 30000;

// ============================================================================
// Route: /booking/success
// ============================================================================

/**
 * Search params for the success page after Stripe redirect.
 *
 * Stripe automatically appends `session_id` via the {CHECKOUT_SESSION_ID}
 * template in the success_url.
 *
 * @see FR-006, FR-010
 */
export const successPageParamsSchema = z.object({
  /** Stripe Checkout Session ID (cs_xxx) */
  session_id: z
    .string()
    .min(1, "Session ID is required")
    .regex(/^cs_(test_|live_)?[a-zA-Z0-9]+$/, "Invalid Stripe session ID format"),
});

export type SuccessPageParams = z.infer<typeof successPageParamsSchema>;

/**
 * Props for the SuccessPage server component.
 */
export interface SuccessPageProps {
  searchParams: Promise<Partial<SuccessPageParams>>;
}

// ============================================================================
// Route: /booking/cancel
// ============================================================================

/**
 * Search params for the cancel page.
 * No query params expected - state restored from sessionStorage.
 *
 * @see FR-011, FR-012
 */
export const cancelPageParamsSchema = z.object({}).optional();

export type CancelPageParams = z.infer<typeof cancelPageParamsSchema>;

/**
 * Props for the CancelPage server component.
 */
export interface CancelPageProps {
  searchParams: Promise<Partial<CancelPageParams>>;
}

// ============================================================================
// Payment Display Status
// ============================================================================

/**
 * Payment status for UI display.
 * Maps backend TransactionStatus to user-friendly states.
 *
 * @see FR-015, FR-016
 */
export const paymentDisplayStatusSchema = z.enum([
  "pending", // Awaiting payment
  "processing", // Returned from Stripe, verifying
  "paid", // Payment confirmed
  "failed", // Payment declined/errored
  "refunded", // Payment refunded
]);

export type PaymentDisplayStatus = z.infer<typeof paymentDisplayStatusSchema>;

/**
 * Configuration for each payment status display.
 */
export interface PaymentStatusConfig {
  status: PaymentDisplayStatus;
  label: string;
  variant: "default" | "secondary" | "destructive" | "outline";
  description: string;
  showRetry: boolean;
  showComplete: boolean;
}

/**
 * Status display configuration map.
 *
 * @see FR-015, FR-016, FR-017
 */
export const PAYMENT_STATUS_CONFIG: Record<
  PaymentDisplayStatus,
  PaymentStatusConfig
> = {
  pending: {
    status: "pending",
    label: "Payment Required",
    variant: "secondary",
    description: "Complete payment to confirm your booking",
    showRetry: false,
    showComplete: true,
  },
  processing: {
    status: "processing",
    label: "Processing...",
    variant: "outline",
    description: "Verifying your payment",
    showRetry: false,
    showComplete: false,
  },
  paid: {
    status: "paid",
    label: "Paid",
    variant: "default",
    description: "Your booking is confirmed",
    showRetry: false,
    showComplete: false,
  },
  failed: {
    status: "failed",
    label: "Payment Failed",
    variant: "destructive",
    description: "Your payment could not be processed",
    showRetry: true,
    showComplete: false,
  },
  refunded: {
    status: "refunded",
    label: "Refunded",
    variant: "outline",
    description: "Your payment has been refunded",
    showRetry: false,
    showComplete: false,
  },
};

// ============================================================================
// Validation Helpers
// ============================================================================

/**
 * Validate success page search params.
 *
 * @param params - Search params from URL
 * @returns Parsed params if valid, or throws ZodError
 */
export function validateSuccessParams(params: unknown): SuccessPageParams {
  return successPageParamsSchema.parse(params);
}

/**
 * Safely validate success page search params.
 *
 * @param params - Search params from URL
 * @returns SafeParseResult with success flag and data/error
 */
export function safeValidateSuccessParams(
  params: unknown
): z.SafeParseReturnType<unknown, SuccessPageParams> {
  return successPageParamsSchema.safeParse(params);
}

/**
 * Check if retry is allowed based on attempt count.
 *
 * @param attempts - Current number of payment attempts
 * @returns true if retry is allowed (< MAX_PAYMENT_ATTEMPTS)
 */
export function canRetryPayment(attempts: number): boolean {
  return attempts < MAX_PAYMENT_ATTEMPTS;
}

/**
 * Get display config for a payment status.
 *
 * @param status - Payment display status
 * @returns PaymentStatusConfig for the status
 */
export function getPaymentStatusConfig(
  status: PaymentDisplayStatus
): PaymentStatusConfig {
  return PAYMENT_STATUS_CONFIG[status];
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for PaymentDisplayStatus.
 */
export function isPaymentDisplayStatus(
  value: unknown
): value is PaymentDisplayStatus {
  return paymentDisplayStatusSchema.safeParse(value).success;
}
