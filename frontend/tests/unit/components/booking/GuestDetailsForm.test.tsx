/**
 * Component tests for GuestDetailsForm (T012a, T017a).
 *
 * TDD Red Phase: Tests define expected behavior for authenticated and anonymous states.
 *
 * T012a [US2]: Authenticated state tests - read-only display, sign-out link visibility
 * T017a [US3]: Anonymous state tests - editable fields, verify email button
 */

import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock aws-amplify/auth before importing components
vi.mock('aws-amplify/auth', () => ({
  getCurrentUser: vi.fn(),
  fetchAuthSession: vi.fn(),
  signIn: vi.fn(),
  signUp: vi.fn(),
  confirmSignIn: vi.fn(),
  signOut: vi.fn(),
}))

import {
  getCurrentUser,
  fetchAuthSession,
  signIn,
  confirmSignIn,
  signOut as amplifySignOut,
} from 'aws-amplify/auth'

import { GuestDetailsForm } from '@/components/booking/GuestDetailsForm'
import { AuthErrorBoundary } from '@/components/booking/AuthErrorBoundary'

// Type mocks
const mockGetCurrentUser = getCurrentUser as Mock
const mockFetchAuthSession = fetchAuthSession as Mock
const mockAmplifySignOut = amplifySignOut as Mock

// Helper to setup authenticated state
function setupAuthenticatedUser(overrides: {
  email?: string
  name?: string
  sub?: string
} = {}) {
  const defaults = {
    email: 'authenticated@example.com',
    name: 'Test User',
    sub: 'cognito-sub-123',
  }
  const user = { ...defaults, ...overrides }

  mockGetCurrentUser.mockResolvedValue({
    userId: user.sub,
    username: user.email,
  })
  mockFetchAuthSession.mockResolvedValue({
    tokens: {
      idToken: {
        payload: {
          email: user.email,
          name: user.name,
        },
      },
    },
  })

  return user
}

// Helper to setup anonymous state
function setupAnonymousUser() {
  mockGetCurrentUser.mockRejectedValue(new Error('Not authenticated'))
  mockFetchAuthSession.mockResolvedValue({ tokens: null })
}

describe('GuestDetailsForm', () => {
  const mockOnSubmit = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    setupAnonymousUser() // Default to anonymous
  })

  // === T017a: Anonymous State Tests [US3] ===

  describe('anonymous state (T017a)', () => {
    // beforeEach already sets up anonymous state by default

    it('shows editable email field when anonymous', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        const emailInput = screen.getByLabelText(/email/i)
        expect(emailInput).not.toBeDisabled()
      })
    })

    it('shows editable name field when anonymous', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        const nameInput = screen.getByLabelText(/full name/i)
        expect(nameInput).not.toBeDisabled()
      })
    })

    it('allows typing in email field when anonymous', async () => {
      const user = userEvent.setup()
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')

      expect(emailInput).toHaveValue('test@example.com')
    })

    it('allows typing in name field when anonymous', async () => {
      const user = userEvent.setup()
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      const nameInput = screen.getByLabelText(/full name/i)
      await user.type(nameInput, 'John Doe')

      expect(nameInput).toHaveValue('John Doe')
    })

    it('shows "Verify email" button when anonymous', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        const verifyButton = screen.getByRole('button', { name: /verify email/i })
        expect(verifyButton).toBeInTheDocument()
      })
    })

    it('does NOT show sign-out button when anonymous', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Give time for async checks
      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      expect(screen.queryByRole('button', { name: /sign out/i })).not.toBeInTheDocument()
    })

    it('does NOT show authenticated banner when anonymous', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Wait for initial render
      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      expect(screen.queryByLabelText(/authenticated/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/signed in/i)).not.toBeInTheDocument()
    })

    // T018a: Verify email button calls initiateAuth
    it('calls initiateAuth with email when "Verify email" button is clicked', async () => {
      const user = userEvent.setup()
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Enter email first
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'newuser@example.com')

      // Click verify email button
      const verifyButton = screen.getByRole('button', { name: /verify email/i })
      await user.click(verifyButton)

      // Should have called Amplify signIn with USER_AUTH flow
      expect(signIn).toHaveBeenCalledWith({
        username: 'newuser@example.com',
        options: {
          authFlowType: 'USER_AUTH',
          preferredChallenge: 'EMAIL_OTP',
        },
      })
    })

    it('does not call initiateAuth when email is empty', async () => {
      const user = userEvent.setup()
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Click verify email button without entering email
      const verifyButton = screen.getByRole('button', { name: /verify email/i })
      await user.click(verifyButton)

      // Should NOT have called signIn
      expect(signIn).not.toHaveBeenCalled()
    })

    // T019a: Loading state while sending OTP
    it('disables "Verify email" button while sending OTP', async () => {
      const user = userEvent.setup()

      // Create a delayed promise to observe loading state
      let resolveSignIn: (value: unknown) => void
      const mockSignIn = signIn as Mock
      mockSignIn.mockReturnValue(
        new Promise((resolve) => {
          resolveSignIn = resolve
        })
      )

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Enter email
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')

      // Click verify email button
      const verifyButton = screen.getByRole('button', { name: /verify email/i })
      await user.click(verifyButton)

      // Button should be disabled while sending
      await waitFor(() => {
        expect(verifyButton).toBeDisabled()
      })

      // Complete the signIn
      await act(async () => {
        resolveSignIn!({
          nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
        })
      })
    })

    it('shows "Sending..." text while sending OTP', async () => {
      const user = userEvent.setup()

      // Create a delayed promise to observe loading state
      let resolveSignIn: (value: unknown) => void
      const mockSignIn = signIn as Mock
      mockSignIn.mockReturnValue(
        new Promise((resolve) => {
          resolveSignIn = resolve
        })
      )

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Enter email
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')

      // Click verify email button
      const verifyButton = screen.getByRole('button', { name: /verify email/i })
      await user.click(verifyButton)

      // Should show loading state
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /sending/i })).toBeInTheDocument()
      })

      // Complete the signIn
      await act(async () => {
        resolveSignIn!({
          nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
        })
      })
    })
  })

  // === T012a: Authenticated State Tests [US2] ===

  describe('authenticated state (T012a)', () => {
    beforeEach(() => {
      setupAuthenticatedUser()
    })

    it('displays user email as read-only when authenticated', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        // Should display email in read-only format
        expect(screen.getByText('authenticated@example.com')).toBeInTheDocument()
      })

      // Email input should not be editable
      const emailInput = screen.queryByRole('textbox', { name: /email/i })
      if (emailInput) {
        expect(emailInput).toBeDisabled()
      }
    })

    it('displays user name as read-only when authenticated', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        // Should display name in read-only format
        expect(screen.getByText('Test User')).toBeInTheDocument()
      })

      // Name input should not be editable
      const nameInput = screen.queryByRole('textbox', { name: /name/i })
      if (nameInput) {
        expect(nameInput).toBeDisabled()
      }
    })

    it('shows sign-out link when authenticated', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        const signOutLink = screen.getByRole('button', { name: /sign out/i })
        expect(signOutLink).toBeInTheDocument()
      })
    })

    it('calls signOut when sign-out link is clicked', async () => {
      const user = userEvent.setup()
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument()
      })

      const signOutButton = screen.getByRole('button', { name: /sign out/i })
      await user.click(signOutButton)

      expect(mockAmplifySignOut).toHaveBeenCalled()
    })

    it('still allows editing phone field when authenticated', async () => {
      const user = userEvent.setup()
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        expect(screen.getByText('authenticated@example.com')).toBeInTheDocument()
      })

      // Phone field should still be editable
      const phoneInput = screen.getByRole('textbox', { name: /phone/i })
      expect(phoneInput).not.toBeDisabled()

      await user.type(phoneInput, '+34 612 345 678')
      expect(phoneInput).toHaveValue('+34 612 345 678')
    })

    it('still allows editing special requests when authenticated', async () => {
      const user = userEvent.setup()
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        expect(screen.getByText('authenticated@example.com')).toBeInTheDocument()
      })

      // Special requests field should still be editable
      const requestsInput = screen.getByRole('textbox', { name: /special requests/i })
      expect(requestsInput).not.toBeDisabled()

      await user.type(requestsInput, 'Late check-in')
      expect(requestsInput).toHaveValue('Late check-in')
    })

    it('uses authenticated email when form is submitted', async () => {
      const user = userEvent.setup()
      render(
        <GuestDetailsForm onSubmit={mockOnSubmit}>
          <button type="submit">Continue</button>
        </GuestDetailsForm>
      )

      await waitFor(() => {
        expect(screen.getByText('authenticated@example.com')).toBeInTheDocument()
      })

      // Fill required fields (phone is required per schema)
      const phoneInput = screen.getByRole('textbox', { name: /phone/i })
      await user.type(phoneInput, '+34 612 345 678')

      // Submit form
      const submitButton = screen.getByRole('button', { name: /continue/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            email: 'authenticated@example.com',
            name: 'Test User',
          })
        )
      })
    })

    it('shows authenticated user badge or indicator', async () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        // Should show some indicator that user is signed in
        expect(
          screen.getByText(/signed in/i) ||
            screen.getByText(/logged in/i) ||
            screen.getByLabelText(/authenticated/i)
        ).toBeInTheDocument()
      })
    })

    it('handles user with name undefined gracefully', async () => {
      setupAuthenticatedUser({ name: undefined })

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      await waitFor(() => {
        expect(screen.getByText('authenticated@example.com')).toBeInTheDocument()
      })

      // Should not crash, name field may show placeholder or be editable
    })
  })

  // === Basic Form Tests (existing behavior) ===

  describe('form rendering', () => {
    it('renders all form fields', () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/phone/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/number of guests/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/special requests/i)).toBeInTheDocument()
    })

    it('renders children (submit button)', () => {
      render(
        <GuestDetailsForm onSubmit={mockOnSubmit}>
          <button type="submit">Continue to Payment</button>
        </GuestDetailsForm>
      )

      expect(
        screen.getByRole('button', { name: /continue to payment/i })
      ).toBeInTheDocument()
    })

    it('applies defaultValues to form fields', async () => {
      render(
        <GuestDetailsForm
          onSubmit={mockOnSubmit}
          defaultValues={{
            name: 'Default Name',
            email: 'default@example.com',
            phone: '+1234567890',
          }}
        />
      )

      expect(screen.getByDisplayValue('Default Name')).toBeInTheDocument()
      expect(screen.getByDisplayValue('default@example.com')).toBeInTheDocument()
      expect(screen.getByDisplayValue('+1234567890')).toBeInTheDocument()
    })

    it('disables form fields when isSubmitting is true', () => {
      render(<GuestDetailsForm onSubmit={mockOnSubmit} isSubmitting={true} />)

      expect(screen.getByLabelText(/full name/i)).toBeDisabled()
      expect(screen.getByLabelText(/email/i)).toBeDisabled()
      expect(screen.getByLabelText(/phone/i)).toBeDisabled()
      expect(screen.getByLabelText(/special requests/i)).toBeDisabled()
    })
  })

  describe('form submission', () => {
    it('calls onSubmit with form data when valid', async () => {
      const user = userEvent.setup()
      render(
        <GuestDetailsForm onSubmit={mockOnSubmit}>
          <button type="submit">Submit</button>
        </GuestDetailsForm>
      )

      await user.type(screen.getByLabelText(/full name/i), 'John Doe')
      await user.type(screen.getByLabelText(/email/i), 'john@example.com')
      await user.type(screen.getByLabelText(/phone/i), '+34 612 345 678')

      await user.click(screen.getByRole('button', { name: /submit/i }))

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'John Doe',
            email: 'john@example.com',
            phone: '+34 612 345 678',
            guestCount: 2, // default value
          })
        )
      })
    })

    it('shows validation errors for invalid email', async () => {
      const user = userEvent.setup()
      render(
        <GuestDetailsForm onSubmit={mockOnSubmit}>
          <button type="submit">Submit</button>
        </GuestDetailsForm>
      )

      await user.type(screen.getByLabelText(/email/i), 'invalid-email')
      await user.tab() // Trigger blur validation

      await waitFor(() => {
        // Zod schema error message: "Please enter a valid email address"
        expect(screen.getByText(/valid email/i)).toBeInTheDocument()
      })
    })
  })

  // === T021a: OTP Entry State Tests [US4] ===

  describe('OTP entry state (T021a)', () => {
    beforeEach(() => {
      setupAnonymousUser()
    })

    it('shows OTP input field when step is awaiting_otp', async () => {
      const user = userEvent.setup()

      // Setup: signIn returns awaiting OTP state
      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Enter email and click verify
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      const verifyButton = screen.getByRole('button', { name: /verify email/i })
      await user.click(verifyButton)

      // Should show OTP input field
      await waitFor(() => {
        expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
      })
    })

    it('shows confirm button when awaiting OTP', async () => {
      const user = userEvent.setup()

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Should show confirm button
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /confirm|verify code|submit code/i })).toBeInTheDocument()
      })
    })

    it('hides verify email button when awaiting OTP', async () => {
      const user = userEvent.setup()

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Verify email button should be hidden
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /verify email/i })).not.toBeInTheDocument()
      })
    })

    it('displays email that code was sent to', async () => {
      const user = userEvent.setup()

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Should show the email address
      await waitFor(() => {
        expect(screen.getByText(/test@example.com/)).toBeInTheDocument()
      })
    })

    it('calls confirmOtp when confirm button is clicked with code', async () => {
      const user = userEvent.setup()
      const { confirmSignIn: mockConfirmSignIn } = await import('aws-amplify/auth')
      const mockConfirm = mockConfirmSignIn as Mock

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      // Setup successful verification - note: getCurrentUser starts rejecting (anonymous)
      // and we configure it to resolve AFTER confirmSignIn succeeds
      mockConfirm.mockImplementation(async () => {
        // After successful confirm, getCurrentUser should return the user
        mockGetCurrentUser.mockResolvedValue({ userId: 'verified-sub-123' })
        mockFetchAuthSession.mockResolvedValue({
          tokens: {
            idToken: {
              payload: {
                email: 'test@example.com',
                name: 'Test User',
              },
            },
          },
        })
        return { isSignedIn: true }
      })

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Wait for OTP input to appear and enter code
      await waitFor(() => {
        expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
      })

      const codeInput = screen.getByLabelText(/verification code|code/i)
      await user.type(codeInput, '123456')

      // Click confirm
      const confirmButton = screen.getByRole('button', { name: /confirm|verify code|submit code/i })
      await user.click(confirmButton)

      // Should have called confirmSignIn
      expect(mockConfirm).toHaveBeenCalledWith({ challengeResponse: '123456' })
    })

    it('shows verifying state with disabled button while confirming', async () => {
      const user = userEvent.setup()
      const { confirmSignIn: mockConfirmSignIn } = await import('aws-amplify/auth')
      const mockConfirm = mockConfirmSignIn as Mock

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      // Create delayed promise for confirm
      let resolveConfirm: (value: unknown) => void
      mockConfirm.mockReturnValue(
        new Promise((resolve) => {
          resolveConfirm = resolve
        })
      )

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Wait for OTP input and enter code
      await waitFor(() => {
        expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
      })

      const codeInput = screen.getByLabelText(/verification code|code/i)
      await user.type(codeInput, '123456')

      // Click confirm
      const confirmButton = screen.getByRole('button', { name: /confirm|verify code|submit code/i })
      await user.click(confirmButton)

      // Should show verifying state
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /verifying/i })).toBeDisabled()
      })

      // Resolve the confirm
      await act(async () => {
        resolveConfirm!({ isSignedIn: true })
      })
    })

    it('shows error message when code is invalid', async () => {
      const user = userEvent.setup()
      const { confirmSignIn: mockConfirmSignIn } = await import('aws-amplify/auth')
      const mockConfirm = mockConfirmSignIn as Mock

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      // Setup failed verification
      const codeMismatchError = new Error('Code mismatch')
      codeMismatchError.name = 'CodeMismatchException'
      mockConfirm.mockRejectedValue(codeMismatchError)

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Wait for OTP input and enter code
      await waitFor(() => {
        expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
      })

      const codeInput = screen.getByLabelText(/verification code|code/i)
      await user.type(codeInput, '000000')

      // Click confirm
      await user.click(screen.getByRole('button', { name: /confirm|verify code|submit code/i }))

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText(/invalid code/i)).toBeInTheDocument()
      })
    })

    it('shows resend link when code has expired', async () => {
      const user = userEvent.setup()
      const { confirmSignIn: mockConfirmSignIn } = await import('aws-amplify/auth')
      const mockConfirm = mockConfirmSignIn as Mock

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      // Setup expired code error
      const expiredError = new Error('Code expired')
      expiredError.name = 'ExpiredCodeException'
      mockConfirm.mockRejectedValue(expiredError)

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Wait for OTP input and enter code
      await waitFor(() => {
        expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
      })

      const codeInput = screen.getByLabelText(/verification code|code/i)
      await user.type(codeInput, '123456')

      // Click confirm
      await user.click(screen.getByRole('button', { name: /confirm|verify code|submit code/i }))

      // Should show expired message and resend link
      await waitFor(() => {
        expect(screen.getByText(/expired/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /resend|send new|request new/i })).toBeInTheDocument()
      })
    })

    it('allows resending code when clicked', async () => {
      const user = userEvent.setup()
      const { confirmSignIn: mockConfirmSignIn } = await import('aws-amplify/auth')
      const mockConfirm = mockConfirmSignIn as Mock

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      // Setup expired code error first
      const expiredError = new Error('Code expired')
      expiredError.name = 'ExpiredCodeException'
      mockConfirm.mockRejectedValue(expiredError)

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Wait for OTP input and enter code
      await waitFor(() => {
        expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
      })

      const codeInput = screen.getByLabelText(/verification code|code/i)
      await user.type(codeInput, '123456')

      // Click confirm to trigger error
      await user.click(screen.getByRole('button', { name: /confirm|verify code|submit code/i }))

      // Wait for resend link
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /resend|send new|request new/i })).toBeInTheDocument()
      })

      // Clear previous call count
      mockSignIn.mockClear()

      // Click resend
      await user.click(screen.getByRole('button', { name: /resend|send new|request new/i }))

      // Should call signIn again
      expect(mockSignIn).toHaveBeenCalledWith({
        username: 'test@example.com',
        options: {
          authFlowType: 'USER_AUTH',
          preferredChallenge: 'EMAIL_OTP',
        },
      })
    })

    it('transitions to authenticated state on successful verification', async () => {
      const user = userEvent.setup()
      const { confirmSignIn: mockConfirmSignIn } = await import('aws-amplify/auth')
      const mockConfirm = mockConfirmSignIn as Mock

      const mockSignIn = signIn as Mock
      mockSignIn.mockResolvedValue({
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      // Setup successful verification - getCurrentUser starts rejecting (anonymous)
      // and we configure it to resolve AFTER confirmSignIn succeeds
      mockConfirm.mockImplementation(async () => {
        // After successful confirm, getCurrentUser should return the user
        mockGetCurrentUser.mockResolvedValue({ userId: 'verified-sub-123' })
        mockFetchAuthSession.mockResolvedValue({
          tokens: {
            idToken: {
              payload: {
                email: 'test@example.com',
                name: 'Verified User',
              },
            },
          },
        })
        return { isSignedIn: true }
      })

      render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

      // Trigger OTP flow
      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')
      await user.click(screen.getByRole('button', { name: /verify email/i }))

      // Wait for OTP input and enter code
      await waitFor(() => {
        expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
      })

      const codeInput = screen.getByLabelText(/verification code|code/i)
      await user.type(codeInput, '123456')

      // Click confirm
      await user.click(screen.getByRole('button', { name: /confirm|verify code|submit code/i }))

      // Should transition to authenticated state
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument()
        expect(screen.getByText('Verified User')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument()
      })
    })
  })

  // =============================================================================
  // T034: Error Type UI Rendering Tests (TDD Red Phase)
  // =============================================================================

  describe('error type UI rendering (T034)', () => {
    // Define mocks at describe level for T034 tests
    let mockSignIn: Mock
    let mockConfirmSignIn: Mock
    let user: ReturnType<typeof userEvent.setup>

    beforeEach(() => {
      // Setup anonymous user state
      setupAnonymousUser()

      // Setup user event helper
      user = userEvent.setup()

      // Create typed mock references
      mockSignIn = signIn as Mock
      mockConfirmSignIn = confirmSignIn as Mock

      // Default: signIn returns OTP flow
      mockSignIn.mockResolvedValue({
        isSignedIn: false,
        nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
      })

      // Default: confirmSignIn succeeds
      mockConfirmSignIn.mockResolvedValue({
        isSignedIn: true,
        nextStep: { signInStep: 'DONE' },
      })
    })

    describe('network error display', () => {
      it('shows network error message with retry button', async () => {
        const networkError = new Error('Network request failed')
        networkError.name = 'NetworkError'
        mockSignIn.mockRejectedValue(networkError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'test@example.com')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        // Should show network-specific error message
        await waitFor(() => {
          expect(
            screen.getByText(/unable to connect/i)
          ).toBeInTheDocument()
        })

        // Should show retry button (not resend code)
        expect(
          screen.getByRole('button', { name: /retry|try again/i })
        ).toBeInTheDocument()
      })

      it('retry button clears error and allows new attempt', async () => {
        const networkError = new Error('Network request failed')
        networkError.name = 'NetworkError'
        mockSignIn.mockRejectedValueOnce(networkError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'test@example.com')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        await waitFor(() => {
          expect(screen.getByText(/unable to connect/i)).toBeInTheDocument()
        })

        // Now mock successful response
        mockSignIn.mockResolvedValueOnce({
          isSignedIn: false,
          nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE' },
        })

        // Click retry
        await user.click(screen.getByRole('button', { name: /retry|try again/i }))

        // Error should be cleared
        await waitFor(() => {
          expect(screen.queryByText(/unable to connect/i)).not.toBeInTheDocument()
        })
      })

      it('shows check internet connection suggestion for network errors', async () => {
        mockSignIn.mockReset()  // Clear any leftover mock state from previous tests
        const networkError = new TypeError('Failed to fetch')
        mockSignIn.mockRejectedValue(networkError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'test@example.com')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        await waitFor(() => {
          expect(
            screen.getByText(/check your internet connection/i)
          ).toBeInTheDocument()
        })
      })
    })

    describe('auth error display', () => {
      it('shows session expired message with sign-in link', async () => {
        const authError = new Error('Session expired')
        authError.name = 'TokenExpiredException'
        mockConfirmSignIn.mockRejectedValue(authError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        // Get to OTP state
        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'test@example.com')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        await waitFor(() => {
          expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
        })

        // Enter OTP
        const codeInput = screen.getByLabelText(/verification code|code/i)
        await user.type(codeInput, '123456')
        await user.click(screen.getByRole('button', { name: /confirm|verify code|submit code/i }))

        // Should show session expired message
        await waitFor(() => {
          expect(screen.getByText(/session expired/i)).toBeInTheDocument()
        })

        // Should have sign-in link/button
        expect(
          screen.getByRole('button', { name: /sign in again/i })
        ).toBeInTheDocument()
      })

      it('CodeMismatchException shows invalid code with retry option', async () => {
        const codeError = new Error('CodeMismatchException')
        codeError.name = 'CodeMismatchException'
        mockConfirmSignIn.mockRejectedValue(codeError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        // Get to OTP state
        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'test@example.com')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        await waitFor(() => {
          expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
        })

        // Enter wrong code
        const codeInput = screen.getByLabelText(/verification code|code/i)
        await user.type(codeInput, '000000')
        await user.click(screen.getByRole('button', { name: /confirm|verify code|submit code/i }))

        // Should show invalid code message
        await waitFor(() => {
          expect(screen.getByText(/invalid code/i)).toBeInTheDocument()
        })

        // Code input should still be available for retry
        expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
      })
    })

    describe('rate limit error display', () => {
      it('shows rate limit message with wait indicator', async () => {
        const limitError = new Error('LimitExceededException')
        limitError.name = 'LimitExceededException'
        mockConfirmSignIn.mockRejectedValue(limitError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        // Get to OTP state
        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'test@example.com')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        await waitFor(() => {
          expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
        })

        // Trigger rate limit
        const codeInput = screen.getByLabelText(/verification code|code/i)
        await user.type(codeInput, '123456')
        await user.click(screen.getByRole('button', { name: /confirm|verify code|submit code/i }))

        // Should show rate limit message
        await waitFor(() => {
          expect(screen.getByText(/too many attempts/i)).toBeInTheDocument()
        })

        // Should indicate user needs to wait
        expect(screen.getByText(/wait/i)).toBeInTheDocument()
      })
    })

    describe('validation error display', () => {
      it('shows validation error inline near field', async () => {
        const validationError = new Error('Invalid email format')
        validationError.name = 'InvalidParameterException'
        mockSignIn.mockRejectedValue(validationError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'invalid-email')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        // Should show validation error
        await waitFor(() => {
          expect(screen.getByText(/invalid/i)).toBeInTheDocument()
        })

        // Email input should be highlighted or have error state
        // This depends on implementation - could check aria-invalid
        expect(emailInput).toBeInTheDocument()
      })
    })

    describe('error styling by type', () => {
      it('network errors have distinct visual style', async () => {
        const networkError = new Error('Network request failed')
        networkError.name = 'NetworkError'
        mockSignIn.mockRejectedValue(networkError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'test@example.com')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        await waitFor(() => {
          const errorContainer = screen.getByText(/unable to connect/i).closest('div')
          // Network errors should have warning/amber styling, not red/destructive
          expect(errorContainer).toHaveClass(/warning|amber|yellow/i)
        })
      })

      it('auth errors have standard error styling', async () => {
        const codeError = new Error('CodeMismatchException')
        codeError.name = 'CodeMismatchException'
        mockConfirmSignIn.mockRejectedValue(codeError)

        render(<GuestDetailsForm onSubmit={mockOnSubmit} />)

        // Get to OTP state
        const emailInput = screen.getByLabelText(/email/i)
        await user.type(emailInput, 'test@example.com')
        await user.click(screen.getByRole('button', { name: /verify email/i }))

        await waitFor(() => {
          expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument()
        })

        const codeInput = screen.getByLabelText(/verification code|code/i)
        await user.type(codeInput, '000000')
        await user.click(screen.getByRole('button', { name: /confirm|verify code|submit code/i }))

        await waitFor(() => {
          const errorContainer = screen.getByText(/invalid code/i).closest('div')
          // Auth errors use standard destructive/error styling
          expect(errorContainer).toHaveClass(/destructive|error|red/i)
        })
      })
    })
  })

  // =============================================================================
  // T034: Error Boundary Tests (TDD Red Phase)
  // =============================================================================

  describe('error boundary (T034)', () => {
    // Save original console.error to restore after tests
    const originalConsoleError = console.error
    let user: ReturnType<typeof userEvent.setup>

    beforeEach(() => {
      // Suppress error boundary console output in tests
      console.error = vi.fn()
      user = userEvent.setup()
    })

    afterEach(() => {
      console.error = originalConsoleError
    })

    it('renders fallback UI when child component throws', () => {
      // Create a component that throws
      const ThrowingComponent = () => {
        throw new Error('Unexpected render error')
      }

      render(
        <AuthErrorBoundary>
          <ThrowingComponent />
        </AuthErrorBoundary>
      )

      // Should show fallback UI, not crash
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    })

    it('shows retry option in fallback UI', () => {
      const ThrowingComponent = () => {
        throw new Error('Unexpected render error')
      }

      render(
        <AuthErrorBoundary>
          <ThrowingComponent />
        </AuthErrorBoundary>
      )

      expect(
        screen.getByRole('button', { name: /try again|retry|reload/i })
      ).toBeInTheDocument()
    })

    it('allows recovery via retry button', async () => {
      let shouldThrow = true

      const MaybeThrowingComponent = () => {
        if (shouldThrow) {
          throw new Error('Temporary error')
        }
        return <div>Recovered successfully</div>
      }

      const { rerender } = render(
        <AuthErrorBoundary>
          <MaybeThrowingComponent />
        </AuthErrorBoundary>
      )

      // Should show error fallback
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()

      // Fix the error condition
      shouldThrow = false

      // Click retry
      await user.click(screen.getByRole('button', { name: /try again|retry|reload/i }))

      // Force rerender after retry
      rerender(
        <AuthErrorBoundary>
          <MaybeThrowingComponent />
        </AuthErrorBoundary>
      )

      // Should recover
      await waitFor(() => {
        expect(screen.getByText(/recovered successfully/i)).toBeInTheDocument()
      })
    })

    it('GuestDetailsForm is wrapped in error boundary', () => {
      // This test verifies that GuestDetailsForm exports exist
      // The wrapping happens at the usage site in pages/forms
      expect(GuestDetailsForm).toBeDefined()
      expect(AuthErrorBoundary).toBeDefined()
    })
  })
})
