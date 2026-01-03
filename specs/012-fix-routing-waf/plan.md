# Implementation Plan: Fix Next.js Routing and WAF 403 Errors

**Branch**: `012-fix-routing-waf` | **Date**: 2026-01-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-fix-routing-waf/spec.md`

## Summary

Fix two routing issues: (1) navbar links missing trailing slashes causing 403 errors, and (2) CloudFront not resolving directory requests to index.html. Additionally, add form data persistence for the booking page on refresh.

**Technical Approach**:
1. Update Navigation.tsx links to use trailing slashes (matches `trailingSlash: true` config)
2. Add CloudFront Function for URL normalization (append trailing slash + index.html)
3. Implement sessionStorage-based form persistence hook for booking page
4. Fix active navigation state detection to handle trailing slash URLs

## Technical Context

**Language/Version**: TypeScript 5.x (frontend), HCL/Terraform >= 1.5.0 (infrastructure)
**Primary Dependencies**: Next.js 14+ (App Router), React, terraform-aws-modules/cloudfront
**Storage**: Browser sessionStorage (form data), S3 (static files)
**Testing**: Vitest (unit), Playwright (E2E)
**Target Platform**: Web browser (static export), AWS CloudFront + S3
**Project Type**: Web application (frontend + infrastructure)
**Performance Goals**: Page load < 3 seconds, navigation instant (client-side)
**Constraints**: Static export only (no server-side rendering), WAF IP whitelist in effect
**Scale/Scope**: 12 public routes, single booking form

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Will write Playwright E2E tests for navigation and form persistence before implementation |
| II. Simplicity & YAGNI | ✅ PASS | Minimal changes: 1 component update, 1 CF function, 1 React hook |
| III. Type Safety | ✅ PASS | TypeScript strict mode, no `any` types needed |
| IV. Observability | ⚪ N/A | Configuration fix - no runtime logging needed |
| V. Incremental Delivery | ✅ PASS | Can deploy navbar fix independently, then CF function, then form persistence |
| VI. Technology Stack | ✅ PASS | Using prescribed stack (Next.js, Terraform modules, no custom UI needed) |

**Gate Result**: ✅ PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/012-fix-routing-waf/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal - form state only)
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── components/
│   │   └── layout/
│   │       └── Navigation.tsx    # UPDATE: Add trailing slashes to links
│   ├── hooks/
│   │   └── useFormPersistence.ts # NEW: sessionStorage form persistence hook
│   └── app/
│       └── book/
│           └── page.tsx          # UPDATE: Use form persistence hook
└── tests/
    └── e2e/
        └── routing.spec.ts       # NEW: Navigation and routing E2E tests

infrastructure/
└── modules/
    └── static-website/
        ├── main.tf               # UPDATE: Add cloudfront_functions block + function_association
        └── functions/
            └── url-rewrite.js    # NEW: CloudFront Function for URL normalization
```

**Structure Decision**: Minimal changes to existing web application structure. One new hook, one new Terraform file, updates to two existing files.

## Complexity Tracking

> No Constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | — | — |
