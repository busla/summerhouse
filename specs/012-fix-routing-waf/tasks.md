# Tasks: Fix Next.js Routing and WAF 403 Errors

**Input**: Design documents from `/specs/012-fix-routing-waf/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**Tests**: E2E tests included per Constitution (Test-First Development). Will use Playwright.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend**: `frontend/src/`, `frontend/tests/`
- **Infrastructure**: `infrastructure/modules/static-website/`

---

## Phase 1: Setup

**Purpose**: Verify current state and prepare for changes

- [x] T001 Verify current issue exists by testing `/gallery/` via CloudFront (expect 403)
- [x] T002 [P] Verify navbar links in `frontend/src/components/layout/Navigation.tsx` use non-trailing-slash paths

---

## Phase 2: Foundational (No blocking prerequisites for this feature)

**Purpose**: This feature modifies existing infrastructure - no new foundational work needed

**Note**: No foundational phase required. All user stories can proceed immediately after verification.

---

## Phase 3: User Story 1 - Navigate Site via Navbar (Priority: P1) 🎯 MVP

**Goal**: Users can navigate between all pages using the navbar without errors, including browser refresh with form persistence

**Independent Test**: Click each navbar link → page loads; refresh on `/book/` → form data preserved

**Requirements Covered**: FR-001, FR-007

### E2E Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T003 [P] [US1] Create E2E test for navbar navigation in `frontend/tests/e2e/routing.spec.ts` - verify clicking each link loads correct page
- [x] T004 [P] [US1] Create E2E test for form persistence in `frontend/tests/e2e/routing.spec.ts` - verify booking form data survives refresh

### Implementation for User Story 1

- [ ] T005 [US1] Update navbar links to use trailing slashes in `frontend/src/components/layout/Navigation.tsx` - change `/gallery` to `/gallery/`, `/book` to `/book/`, etc.
- [ ] T006 [P] [US1] Create `useFormPersistence` hook in `frontend/src/hooks/useFormPersistence.ts` per research.md specification
- [ ] T007 [US1] Integrate `useFormPersistence` hook into booking page `frontend/src/app/book/page.tsx`
- [ ] T008 [US1] Add `clear()` call after successful booking submission in `frontend/src/app/book/page.tsx`

**Checkpoint**: Navbar navigation works locally; form persistence works; E2E tests pass locally

---

## Phase 4: User Story 2 - Direct URL Access (Priority: P1)

**Goal**: Users can access any page by typing URL directly or refreshing browser without 403 errors

**Independent Test**: Type `https://<cloudfront>/gallery/` in browser → page loads; type `https://<cloudfront>/gallery` (no slash) → page loads

**Requirements Covered**: FR-002, FR-005, FR-006

### E2E Tests for User Story 2

> **NOTE: These tests must run against CloudFront, not local dev server**

- [ ] T009 [P] [US2] Create E2E test for direct URL access in `frontend/tests/e2e/routing.spec.ts` - verify `/gallery/` loads without 403
- [ ] T010 [P] [US2] Create E2E test for URL normalization in `frontend/tests/e2e/routing.spec.ts` - verify `/gallery` (no slash) loads

### Implementation for User Story 2

- [ ] T011 [P] [US2] Create CloudFront Function file `infrastructure/modules/static-website/functions/url-rewrite.js` per research.md specification
- [ ] T012 [US2] Add `cloudfront_functions` block to CloudFront module in `infrastructure/modules/static-website/main.tf`
- [ ] T013 [US2] Add `function_association` for `viewer-request` event in default cache behavior in `infrastructure/modules/static-website/main.tf`
- [ ] T014 [US2] Deploy infrastructure changes with `task tf:apply:dev`
- [ ] T015 [US2] Verify CloudFront Function is associated by checking `task tf:output:dev`

**Checkpoint**: All routes accessible via CloudFront without 403; both URL formats work

---

## Phase 5: User Story 3 - Active Navigation State (Priority: P2)

**Goal**: Navbar visually indicates which page is currently active

**Independent Test**: Navigate to `/gallery/` → "Gallery" link is highlighted; navigate to `/book/` → "Book" link is highlighted

**Requirements Covered**: FR-003

### E2E Tests for User Story 3

- [ ] T016 [P] [US3] Create E2E test for active state in `frontend/tests/e2e/routing.spec.ts` - verify correct nav link has active styling on each page

### Implementation for User Story 3

- [ ] T017 [US3] Add `normalizePathname` helper function in `frontend/src/components/layout/Navigation.tsx` per research.md specification
- [ ] T018 [US3] Update `isActive` logic in Navigation.tsx to use normalized path comparison
- [ ] T019 [US3] Verify active state works for both `/gallery` and `/gallery/` URLs

**Checkpoint**: Active nav state correctly highlights current page regardless of URL format

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation

- [ ] T020 Run full E2E test suite with `task frontend:test` against deployed CloudFront
- [ ] T021 [P] Run verification checklist from quickstart.md (all 8 items)
- [ ] T022 [P] Test edge case: access `/nonexistent/` - should show 404 page (via 403.html)
- [ ] T023 Invalidate CloudFront cache if needed with `aws cloudfront create-invalidation`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verification only
- **Foundational (Phase 2)**: N/A for this feature
- **User Story 1 (Phase 3)**: Can start immediately - frontend-only changes
- **User Story 2 (Phase 4)**: Can start immediately - infrastructure changes
- **User Story 3 (Phase 5)**: Depends on US1 (needs trailing-slash links)
- **Polish (Phase 6)**: Depends on US1 + US2 completion (need deployed infrastructure)

### User Story Dependencies

```
US1 (Navbar) ←──┐
                ├── US3 (Active State) depends on trailing-slash links from US1
US2 (CloudFront) ←── Independent, but needed for full E2E testing
```

### Within Each User Story

1. E2E tests FIRST - verify they FAIL
2. Implementation tasks in order
3. Verify E2E tests PASS
4. Checkpoint validation

### Parallel Opportunities

**Within Phase 3 (US1):**
```bash
# These can run in parallel (different files):
T003: E2E test for navbar navigation
T004: E2E test for form persistence
T006: Create useFormPersistence hook (after T005)
```

**Within Phase 4 (US2):**
```bash
# These can run in parallel (different files):
T009: E2E test for direct URL access
T010: E2E test for URL normalization
T011: Create CloudFront Function file
```

**Across Phases (after Setup):**
```bash
# US1 and US2 can run in parallel by different developers:
Developer A: T003-T008 (Frontend changes)
Developer B: T009-T015 (Infrastructure changes)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify issue exists)
2. Complete Phase 3: User Story 1 (navbar + form persistence)
3. **STOP and VALIDATE**: Test navbar locally with `task frontend:dev`
4. Note: Full CloudFront testing requires US2

### Incremental Delivery

1. US1 → Local navbar works, form persists on refresh
2. US2 → Deploy CF function → Full CloudFront routing works
3. US3 → Active state polish
4. Each story adds value without breaking previous stories

### Recommended Order (Solo Developer)

```
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 (US1 complete)
     → T011 → T012 → T013 → T014 → T015 (US2 complete)
     → T009 → T010 (US2 E2E tests - need deployed infra)
     → T016 → T017 → T018 → T019 (US3 complete)
     → T020 → T021 → T022 → T023 (Polish)
```

---

## Task Summary

| Phase | Story | Task Count | Parallel Tasks |
|-------|-------|------------|----------------|
| Setup | — | 2 | 1 |
| Foundational | — | 0 | — |
| US1 (Navbar) | P1 | 6 | 3 |
| US2 (CloudFront) | P1 | 7 | 3 |
| US3 (Active State) | P2 | 4 | 1 |
| Polish | — | 4 | 2 |
| **Total** | | **23** | **10** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- E2E tests against CloudFront require US2 deployment
- Form persistence only affects `/book/` page per clarification
- CloudFront Function handles both trailing-slash and non-trailing-slash URLs
