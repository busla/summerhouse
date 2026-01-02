/**
 * Booking Form Validation Schema
 *
 * Zod schemas for validating booking form inputs (FR-012, FR-013).
 * These schemas mirror the backend Pydantic models and ensure
 * consistent validation between frontend and backend.
 *
 * @see specs/009-booking-frontend/spec.md - FR-012, FR-013, FR-013a
 * @see backend/shared/src/shared/models/reservation.py
 */

import { z } from "zod";

// ============================================================================
// Constants (mirror backend constraints)
// ============================================================================

/** Maximum guests allowed for the property (single apartment) */
export const MAX_GUESTS = 4;

/** Minimum guests (at least 1 person booking) */
export const MIN_GUESTS = 1;

// ============================================================================
// Base Schemas
// ============================================================================

/**
 * Email schema with standard validation.
 * Used for guest email verification (FR-013a).
 */
export const emailSchema = z
  .string()
  .min(1, "Email is required")
  .email("Please enter a valid email address")
  .max(254, "Email is too long");

/**
 * Phone number schema with flexible international format.
 * Accepts various formats: +34612345678, 612 345 678, etc.
 */
export const phoneSchema = z
  .string()
  .min(1, "Phone number is required")
  .regex(
    /^[+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]*$/,
    "Please enter a valid phone number"
  )
  .min(7, "Phone number is too short")
  .max(20, "Phone number is too long");

/**
 * Guest name schema.
 * Must be at least 2 characters, reasonable max length.
 */
export const nameSchema = z
  .string()
  .min(1, "Name is required")
  .min(2, "Name must be at least 2 characters")
  .max(100, "Name is too long")
  .regex(/^[a-zA-ZÀ-ÿ\s'-]+$/, "Name contains invalid characters");

/**
 * Number of guests schema (FR-013).
 * Must be between MIN_GUESTS and MAX_GUESTS.
 */
export const numGuestsSchema = z
  .number()
  .int("Number of guests must be a whole number")
  .min(MIN_GUESTS, `At least ${MIN_GUESTS} guest is required`)
  .max(MAX_GUESTS, `Maximum ${MAX_GUESTS} guests allowed`);

/**
 * Optional special requests / notes.
 * Free-form text with reasonable max length.
 */
export const specialRequestsSchema = z
  .string()
  .max(1000, "Special requests are too long")
  .optional();

// ============================================================================
// Date Schemas
// ============================================================================

/**
 * Date string schema (YYYY-MM-DD format).
 * Used for check-in and check-out dates.
 */
export const dateStringSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "Date must be in YYYY-MM-DD format");

/**
 * Future date validation.
 * Ensures the date is not in the past.
 */
export const futureDateSchema = dateStringSchema.refine(
  (dateStr) => {
    const date = new Date(dateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return date >= today;
  },
  { message: "Date cannot be in the past" }
);

// ============================================================================
// Booking Form Schemas
// ============================================================================

/**
 * Guest details form schema (FR-012).
 *
 * Validates the guest information collected during booking:
 * - Name (required)
 * - Email (required, used for verification)
 * - Phone (required)
 * - Number of guests (1-4)
 * - Special requests (optional)
 */
export const guestDetailsSchema = z.object({
  name: nameSchema,
  email: emailSchema,
  phone: phoneSchema,
  numGuests: numGuestsSchema,
  specialRequests: specialRequestsSchema,
});

/**
 * Date range selection schema.
 * Validates check-in and check-out dates with business rules.
 */
export const dateRangeSchema = z
  .object({
    checkIn: futureDateSchema,
    checkOut: dateStringSchema,
  })
  .refine(
    (data) => {
      const checkIn = new Date(data.checkIn);
      const checkOut = new Date(data.checkOut);
      return checkOut > checkIn;
    },
    {
      message: "Check-out date must be after check-in date",
      path: ["checkOut"],
    }
  );

/**
 * Complete booking request schema.
 *
 * Combines date selection and guest details for the full
 * booking form submission. This matches the backend
 * CreateReservationRequest model.
 */
export const bookingRequestSchema = z.object({
  /** Check-in date (YYYY-MM-DD) */
  checkIn: futureDateSchema,
  /** Check-out date (YYYY-MM-DD) */
  checkOut: dateStringSchema,
  /** Guest details */
  guest: guestDetailsSchema,
});

// ============================================================================
// Type Exports
// ============================================================================

/** Inferred type for guest details form data */
export type GuestDetails = z.infer<typeof guestDetailsSchema>;

/** Inferred type for date range selection */
export type DateRange = z.infer<typeof dateRangeSchema>;

/** Inferred type for complete booking request */
export type BookingRequest = z.infer<typeof bookingRequestSchema>;

// ============================================================================
// Validation Helpers
// ============================================================================

/**
 * Validate guest details form.
 *
 * @param data - Form data to validate
 * @returns Parsed data if valid, or throws ZodError
 */
export function validateGuestDetails(data: unknown): GuestDetails {
  return guestDetailsSchema.parse(data);
}

/**
 * Safely validate guest details form.
 *
 * @param data - Form data to validate
 * @returns SafeParseResult with success flag and data/error
 */
export function safeValidateGuestDetails(
  data: unknown
): z.SafeParseReturnType<unknown, GuestDetails> {
  return guestDetailsSchema.safeParse(data);
}

/**
 * Validate complete booking request.
 *
 * @param data - Booking request data to validate
 * @returns Parsed data if valid, or throws ZodError
 */
export function validateBookingRequest(data: unknown): BookingRequest {
  return bookingRequestSchema.parse(data);
}

/**
 * Safely validate complete booking request.
 *
 * @param data - Booking request data to validate
 * @returns SafeParseResult with success flag and data/error
 */
export function safeValidateBookingRequest(
  data: unknown
): z.SafeParseReturnType<unknown, BookingRequest> {
  return bookingRequestSchema.safeParse(data);
}

// ============================================================================
// Error Formatting
// ============================================================================

/**
 * Format Zod errors into a user-friendly map.
 *
 * @param error - ZodError from failed validation
 * @returns Map of field names to error messages
 */
export function formatValidationErrors(
  error: z.ZodError
): Record<string, string> {
  const errors: Record<string, string> = {};

  for (const issue of error.issues) {
    const path = issue.path.join(".");
    // Only keep first error per field
    if (!errors[path]) {
      errors[path] = issue.message;
    }
  }

  return errors;
}
