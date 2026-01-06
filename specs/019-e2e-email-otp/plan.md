# Implementation Plan: E2E Test Support for Cognito Email OTP

**Branch**: `019-e2e-email-otp` | **Date**: 2026-01-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-e2e-email-otp/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Enable E2E tests to use real Cognito EMAIL_OTP authentication by intercepting OTP codes via a Custom Message Lambda Trigger and storing them in DynamoDB. This removes the current `window.__MOCK_AUTH__` workaround and allows tests to exercise the complete 4-step booking flow (Date Selection → Auth/OTP → Guest Details → Payment) exactly as production users experience it.

## Technical Context

**Language/Version**: Python 3.13+ (Lambda), TypeScript strict (E2E tests)
**Primary Dependencies**: AWS Lambda, Cognito Custom Message Trigger, DynamoDB, Playwright
**Storage**: DynamoDB (`verification_codes` table - already exists with TTL enabled)
**Testing**: Playwright (E2E), pytest + moto (Lambda unit tests)
**Target Platform**: AWS Lambda (Python runtime), CI/CD with AWS credentials
**Project Type**: Web application (frontend + backend + infrastructure)
**Performance Goals**: OTP retrieval <500ms p99
**Constraints**: Must NOT modify production auth flow, test-environment-only activation
**Scale/Scope**: E2E test suite (~10-20 concurrent test runs in CI)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Test-First Development** | ✅ PASS | Feature enables TDD by making OTP flows testable |
| **II. Simplicity & YAGNI** | ✅ PASS | Custom Message Lambda is the simplest AWS-native solution; reuses existing `verification_codes` table |
| **III. Type Safety** | ✅ PASS | Lambda uses Python type hints, E2E helper uses TypeScript strict |
| **IV. Observability** | ✅ PASS | Lambda logs OTP interception events with structured JSON |
| **V. Incremental Delivery** | ✅ PASS | P1 (OTP retrieval) delivers value independently of P2/P3 |
| **VI. Technology Stack** | ✅ PASS | Uses terraform-aws-modules, Playwright, existing patterns |

**Pre-Implementation Verification Required**:
- [ ] Confirm Cognito User Pool tier supports Custom Message Lambda (ESSENTIALS required)
- [ ] Verify `verification_codes` table schema matches OTP storage needs

## Project Structure

### Documentation (this feature)

```text
specs/019-e2e-email-otp/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
infrastructure/
├── modules/
│   ├── cognito-passwordless/   # Add Lambda trigger configuration
│   │   └── main.tf
│   ├── dynamodb/               # verification_codes table (exists)
│   │   └── main.tf
│   └── otp-interceptor/        # NEW: Lambda module for OTP interception
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── environments/
    └── dev/
        └── terragrunt.hcl      # Wire up otp-interceptor module

backend/
└── lambdas/
    └── otp-interceptor/        # NEW: Lambda source code
        ├── handler.py
        ├── requirements.txt
        └── tests/
            └── test_handler.py

frontend/
└── tests/
    └── e2e/
        ├── fixtures/
        │   └── auth.fixture.ts  # Update to use OTP retrieval
        └── utils/
            └── otp-helper.ts    # NEW: DynamoDB OTP retrieval helper
```

**Structure Decision**: Web application structure (Option 2). New Lambda module follows existing `infrastructure/modules/` pattern. E2E test helpers added to `frontend/tests/e2e/utils/`.

## Complexity Tracking

> **No violations identified** - solution uses existing patterns and infrastructure.

| Aspect | Evaluation |
|--------|------------|
| New Lambda module | Follows existing module pattern (cognito-passwordless, dynamodb) |
| DynamoDB access from tests | Reuses existing AWS SDK patterns in CI |
| Custom Message Trigger | Standard Cognito feature, well-documented |
