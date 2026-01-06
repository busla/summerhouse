# Quickstart: Booking Authentication Step

**Feature Branch**: `015-booking-auth-step`
**Date**: 2025-01-05
**Estimated Time**: 2-3 days

## Prerequisites

1. **Branch Setup**
   ```bash
   git checkout -b 015-booking-auth-step
   ```

2. **Dependencies**
   ```bash
   task frontend:install
   task backend:install
   ```

3. **Development Servers**
   ```bash
   task dev  # Starts frontend (3000) and backend (3001)
   ```

## Quick Implementation Path

### Step 1: Install shadcn/ui input-otp (15 min)

```bash
cd frontend
npx shadcn@latest add input-otp
```

Verify installation:
```bash
ls src/components/ui/input-otp.tsx
```

### Step 2: Create Auth Schema (30 min)

Create `frontend/src/lib/schemas/auth-step.schema.ts`:

```typescript
import { z } from 'zod'

export const authStepSchema = z.object({
  name: z.string().min(2).max(100).regex(/^[a-zA-ZÀ-ÿ\s'-]+$/),
  email: z.string().email().max(255),
  phone: z.string().min(7).max(20).regex(/^[+\d\s()-]+$/),
})

export const otpSchema = z.object({
  code: z.string().length(6).regex(/^\d{6}$/),
})

export type AuthStepFormData = z.infer<typeof authStepSchema>
export type OtpFormData = z.infer<typeof otpSchema>
```

### Step 3: Create AuthStep Component (2-3 hours)

Create `frontend/src/components/booking/AuthStep.tsx`:

```typescript
'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuthenticatedUser } from '@/hooks/useAuthenticatedUser'
import { authStepSchema, type AuthStepFormData } from '@/lib/schemas/auth-step.schema'

interface AuthStepProps {
  defaultValues?: Partial<AuthStepFormData>
  onAuthenticated: (customerId: string) => void
  onBack: () => void
  onChange?: (values: AuthStepFormData) => void
}

export function AuthStep({ defaultValues, onAuthenticated, onBack, onChange }: AuthStepProps) {
  const [otpCode, setOtpCode] = useState('')
  const { step, error, errorType, initiateAuth, confirmOtp, retry } = useAuthenticatedUser()

  const form = useForm<AuthStepFormData>({
    resolver: zodResolver(authStepSchema),
    defaultValues: {
      name: defaultValues?.name ?? '',
      email: defaultValues?.email ?? '',
      phone: defaultValues?.phone ?? '',
    },
  })

  // Implementation continues...
}
```

### Step 4: Update BookPage (1-2 hours)

Modify `frontend/src/app/book/page.tsx`:

1. Add `'auth'` to `BookingStep` type
2. Add auth fields to `BookingFormState`
3. Import and render `AuthStep` component
4. Update step indicator to show 4 steps

### Step 5: Simplify GuestDetailsForm (1 hour)

Modify `frontend/src/components/booking/GuestDetailsForm.tsx`:

1. Remove name, email, phone fields
2. Remove OTP UI and state
3. Remove `useAuthenticatedUser` integration
4. Keep only guestCount and specialRequests

### Step 6: Write Tests (2-3 hours)

Create `frontend/tests/unit/components/booking/AuthStep.test.tsx`:
- Form validation tests
- Auth state transitions
- OTP input behavior
- Error handling

Create `frontend/tests/e2e/auth-step.spec.ts`:
- Unauthenticated flow (form → OTP UI)
- Authenticated bypass (using auth fixture)

## Key Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `src/components/ui/input-otp.tsx` | CREATE | Via shadcn CLI |
| `src/lib/schemas/auth-step.schema.ts` | CREATE | Zod schemas |
| `src/components/booking/AuthStep.tsx` | CREATE | New component |
| `src/app/book/page.tsx` | MODIFY | Add auth step |
| `src/components/booking/GuestDetailsForm.tsx` | MODIFY | Simplify |
| `tests/unit/.../AuthStep.test.tsx` | CREATE | Unit tests |
| `tests/e2e/auth-step.spec.ts` | CREATE | E2E tests |
| `tests/e2e/direct-booking.spec.ts` | MODIFY | Update for new step |

## Testing Commands

```bash
# Unit tests
cd frontend && yarn test --run

# E2E tests (local)
cd frontend && yarn test:e2e

# E2E tests (live site)
cd frontend && yarn test:e2e --project=live
```

## Verification Checklist

- [ ] `input-otp` component installed
- [ ] AuthStep shows 3 fields (name, email, phone)
- [ ] "Verify Email" triggers OTP flow
- [ ] OTP input shows 6 separate boxes
- [ ] Auto-advance between OTP digits works
- [ ] Customer profile created after OTP verification
- [ ] Authenticated users skip auth step
- [ ] Form state persists across refresh
- [ ] All existing E2E tests pass

## Common Issues

### OTP Not Sending
- Check Cognito User Pool EMAIL_OTP is enabled
- Verify Amplify config in `lib/amplify-config.ts`

### 409 on Customer Creation
- Expected for returning users
- Handle as success, proceed to next step

### E2E Auth Tests Failing
- Ensure SSM parameters exist: `/booking/e2e/test-user-*`
- Or set env vars: `E2E_TEST_USER_EMAIL`, `E2E_TEST_USER_PASSWORD`

## References

- [Spec](./spec.md) - Feature requirements
- [Research](./research.md) - Bug analysis and decisions
- [Data Model](./data-model.md) - Schema definitions
- [Contracts](./contracts/README.md) - API usage
