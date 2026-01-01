# Tasks: REST API Gateway Migration

**Input**: Design documents from `/specs/008-rest-api-gateway/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Testing via `task tf:plan:dev`, `task tf:apply:dev`, and manual endpoint verification (per spec.md). No unit tests required.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Infrastructure**: `infrastructure/modules/gateway-v2/`
- **Backend Scripts**: `backend/api/src/api/scripts/`
- **Specs/Contracts**: `specs/008-rest-api-gateway/`

---

## Phase 1: Setup

**Purpose**: Prepare the module for migration without breaking current state

- [x] T001 [P] Create git branch `008-rest-api-gateway` from main
- [x] T002 [P] Read current module state in `infrastructure/modules/gateway-v2/main.tf`

---

## Phase 2: Foundational (OpenAPI Script Updates)

**Purpose**: Update `generate_openapi.py` to support REST API extensions - MUST be complete before Terraform changes

**⚠️ CRITICAL**: REST API requires different OpenAPI extensions. Script must be updated first.

- [x] T003 [US2] Add `api_type` parameter support in `backend/api/src/api/scripts/generate_openapi.py`
- [x] T004 [US2] Add `aws_account_id` parameter support in `backend/api/src/api/scripts/generate_openapi.py`
- [x] T005 [US2] Change integration type from `AWS_PROXY` to `aws_proxy` for REST API in `backend/api/src/api/scripts/generate_openapi.py`
- [x] T006 [US2] Replace `payloadFormatVersion` with `passthroughBehavior: when_no_match` in `backend/api/src/api/scripts/generate_openapi.py`
- [x] T007 [US3] Change authorizer from `jwt` type to `cognito_user_pools` type in `backend/api/src/api/scripts/generate_openapi.py`
- [x] T008 [US3] Construct `providerARNs` from pool ID and account ID in `backend/api/src/api/scripts/generate_openapi.py`
- [x] T009 [US2] Generate OPTIONS methods with mock integration for CORS in `backend/api/src/api/scripts/generate_openapi.py`
- [x] T010 [US2] Update security scheme from `cognito-jwt` to `CognitoAuthorizer` in `backend/api/src/api/scripts/generate_openapi.py`

**Checkpoint**: OpenAPI script now generates REST API-compatible spec. Validate with `uv run python -m api.scripts.generate_openapi --help`

---

## Phase 3: User Story 1 - Deploy REST API Gateway (Priority: P1) 🎯 MVP

**Goal**: Replace HTTP API resources with REST API resources in Terraform module

**Independent Test**: Run `task tf:plan:dev` - should show destroy of HTTP API resources and create of REST API resources

### Implementation for User Story 1

- [x] T011 [US1] Add `stage_name` variable with validation in `infrastructure/modules/gateway-v2/variables.tf`
- [x] T012 [US1] Add `data.aws_caller_identity.current` data source in `infrastructure/modules/gateway-v2/main.tf`
- [x] T013 [US1] Update `data.external.openapi` query to include `api_type` and `aws_account_id` in `infrastructure/modules/gateway-v2/main.tf`
- [x] T014 [US1] Replace `aws_apigatewayv2_api.main` with `aws_api_gateway_rest_api.main` in `infrastructure/modules/gateway-v2/main.tf`
- [x] T015 [US1] Add `aws_api_gateway_deployment.main` with SHA1 trigger in `infrastructure/modules/gateway-v2/main.tf`
- [x] T016 [US1] Replace `aws_apigatewayv2_stage.default` with `aws_api_gateway_stage.main` in `infrastructure/modules/gateway-v2/main.tf`
- [x] T017 [US1] Update `aws_lambda_permission.api_gateway` ARN pattern from `/*/*` to `/*/*/*` in `infrastructure/modules/gateway-v2/main.tf`
- [x] T018 [US1] Remove legacy `aws_apigatewayv2_integration` and `aws_apigatewayv2_route` resources in `infrastructure/modules/gateway-v2/main.tf`

**Checkpoint**: `task tf:plan:dev` shows clean destroy/create. REST API should be deployable.

---

## Phase 4: User Story 4 - Existing Infrastructure Integration (Priority: P2)

**Goal**: Maintain backward-compatible module interface (inputs/outputs)

**Independent Test**: Compare module inputs/outputs before and after - root module requires no changes

### Implementation for User Story 4

- [x] T019 [US4] Update `api_gateway_url` output to use `aws_api_gateway_stage.main.invoke_url` in `infrastructure/modules/gateway-v2/outputs.tf`
- [x] T020 [US4] Update `api_gateway_id` output to use `aws_api_gateway_rest_api.main.id` in `infrastructure/modules/gateway-v2/outputs.tf`
- [x] T021 [US4] Update `api_gateway_arn` output to use `aws_api_gateway_rest_api.main.execution_arn` in `infrastructure/modules/gateway-v2/outputs.tf`
- [x] T022 [US4] Update `oauth2_callback_url` output to use stage invoke_url in `infrastructure/modules/gateway-v2/outputs.tf`
- [x] T023 [US4] Add `api_gateway_stage_name` output in `infrastructure/modules/gateway-v2/outputs.tf`

**Checkpoint**: Root module (`infrastructure/main.tf`) requires no changes. All outputs remain compatible.

---

## Phase 5: User Story 5 - CloudWatch Logging and Monitoring (Priority: P2)

**Goal**: Enable CloudWatch access logging for REST API (requires account-level IAM role)

**Independent Test**: Make API request, verify log entry appears in CloudWatch log group

### Implementation for User Story 5

- [x] T024 [US5] Add `aws_iam_role.api_gateway_cloudwatch` with assume role policy in `infrastructure/modules/gateway-v2/main.tf`
- [x] T025 [US5] Add `aws_iam_role_policy_attachment.api_gateway_cloudwatch` with managed policy in `infrastructure/modules/gateway-v2/main.tf`
- [x] T026 [US5] Add `aws_api_gateway_account.main` referencing CloudWatch IAM role in `infrastructure/modules/gateway-v2/main.tf`
- [x] T027 [US5] Configure `access_log_settings` block in `aws_api_gateway_stage.main` with JSON format in `infrastructure/modules/gateway-v2/main.tf`

**Checkpoint**: CloudWatch logs capture API requests with requestId, method, path, status, latency.

---

## Phase 6: User Story 2 & 3 Verification

**Goal**: Verify OpenAPI-driven configuration and Cognito JWT authorization work correctly

**Note**: US2 and US3 implementation was completed in Phase 2 (OpenAPI script) and Phase 3 (Terraform resources). This phase validates them.

### Verification for User Story 2 (OpenAPI-Driven Configuration)

- [x] T028 [US2] Validate generated OpenAPI spec against `specs/008-rest-api-gateway/contracts/openapi-rest-api.schema.json` using `check-jsonschema` (`uv run check-jsonschema --schemafile contracts/openapi-rest-api.schema.json generated-openapi.json`)
- [x] T029 [US2] Verify all FastAPI routes appear in deployed REST API via AWS Console or CLI

### Verification for User Story 3 (Cognito JWT Authorization)

- [x] T030 [US3] Test protected endpoint returns 401 without Authorization header
- [x] T031 [US3] Test protected endpoint returns 200 with valid Cognito JWT
- [x] T032 [US3] Test protected endpoint returns 401 with expired JWT

**Note**: T029-T032 require `task tf:apply:dev` to complete (deployment needed for live testing)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation

- [x] T033 [P] Run full `task tf:plan:dev` and verify clean plan
- [x] T034 [P] Run `task tf:apply:dev` and verify deployment succeeds
- [x] T035 [P] Test CORS preflight (OPTIONS) requests return correct headers
- [x] T036 [P] Verify API response latency < 3 seconds
- [x] T037 [P] Run quickstart.md validation scenarios from `specs/008-rest-api-gateway/quickstart.md`
- [x] T038 Update CLAUDE.md with 008-rest-api-gateway feature information (if not already done)
- [x] T039 [SC-006] Verify interface changes documented in `specs/008-rest-api-gateway/contracts/gateway-v2-interface.md` (new `stage_name` input, output source changes)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: OpenAPI script changes - BLOCKS Terraform changes
- **User Story 1 (Phase 3)**: Depends on Phase 2 - core REST API resources
- **User Story 4 (Phase 4)**: Depends on Phase 3 - outputs reference REST API resources
- **User Story 5 (Phase 5)**: Depends on Phase 3 - CloudWatch logging for REST API
- **Verification (Phase 6)**: Depends on Phases 2-5 - validates all stories work
- **Polish (Phase 7)**: Depends on all phases complete

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 (Deploy REST API) | Phase 2 (OpenAPI script) | T010 complete |
| US2 (OpenAPI Config) | None | Phase 1 |
| US3 (Cognito JWT) | US2 (authorizer in OpenAPI) | T007-T008 complete |
| US4 (Integration) | US1 (REST API exists) | T018 complete |
| US5 (CloudWatch) | US1 (REST API stage exists) | T016 complete |

### Parallel Opportunities

```bash
# Phase 2 - These can run in parallel (different functions in same file):
T003, T004 (parameter support)
T005, T006 (integration changes)
T007, T008 (authorizer changes)

# Phase 4 & 5 can run in parallel after Phase 3:
Phase 4: T019-T023 (outputs)
Phase 5: T024-T027 (CloudWatch)

# Phase 7 - All validation tasks can run in parallel:
T033, T034, T035, T036, T037, T038
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: OpenAPI script (US2 + US3 foundation)
3. Complete Phase 3: REST API resources (US1)
4. **STOP and VALIDATE**: `task tf:plan:dev` should show clean migration
5. Run Phase 6 verification for US2 and US3

### Full Migration

1. MVP above
2. Complete Phase 4: Interface compatibility (US4)
3. Complete Phase 5: CloudWatch logging (US5)
4. Complete Phase 7: Polish and validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Testing is via Terraform plan/apply and manual verification (no pytest for infrastructure)
- The OpenAPI script changes (Phase 2) are the foundation - must complete before Terraform changes
- US2 and US3 span multiple phases: script changes in Phase 2, resource changes in Phase 3, verification in Phase 6
- Commit after each task or logical group
- Refer to `quickstart.md` for common issues and troubleshooting
