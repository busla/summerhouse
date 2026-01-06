# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Add dedicated `AuthStep` component (428 lines) with email verification UI for the 4-step booking flow
- Add `useCustomerProfile` hook (256 lines) to sync customer profile with backend after OTP verification
- Add `input-otp` component for 6-digit code entry with auto-advance functionality
- Add backend cleanup utility script for development data management
- Add comprehensive E2E and unit tests for authentication flow covering new and returning customer scenarios

### Changed
- Enhance `useAuthenticatedUser` hook (276+ lines added) with improved Cognito state handling including `CONTINUE_SIGN_IN_WITH_FIRST_FACTOR_SELECTION` support
- Simplify `GuestDetailsForm` component by extracting authentication logic to dedicated step (326 lines reduction)
- Refactor booking flow to include new authentication step between date selection and guest details (now 4-step process)
- Rewrite E2E and unit tests to align with new booking flow structure

### Fixed
- Fix Cognito state machine transitions in authentication flow
- Fix OTP verification flow edge cases and error handling

## [v0.1.0] - 2026-01-05

### Added
- Complete Stripe payment integration with checkout session management
- Playwright E2E tests for payment flows and direct booking

### Fixed
- Route issues in application navigation
- Cognito OTP validation flow

### Changed
- Rename API customer models and remove dead code

---

[Unreleased]: https://github.com/busla/booking/compare/v0.1.0...HEAD
[v0.1.0]: https://github.com/busla/booking/releases/tag/v0.1.0
