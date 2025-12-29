# Tasks: Static Website WAF Protection

**Input**: Design documents from `/specs/002-static-website-waf/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Tests**: Not requested - tasks focus on Terraform implementation with manual validation via `terraform validate` and `terraform plan`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Infrastructure**: `infrastructure/modules/static-website/`
- **Environment configs**: `infrastructure/environments/{dev,prod}/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the module for WAF integration

- [ ] T001 Add AWS provider alias for us-east-1 in `infrastructure/modules/static-website/providers.tf`
- [ ] T002 [P] Add `enable_waf` variable to `infrastructure/modules/static-website/variables.tf`
- [ ] T003 [P] Add `waf_whitelisted_ips` variable with object type and validation to `infrastructure/modules/static-website/variables.tf`
- [ ] T004 [P] Add `waf_managed_rules` variable with optional managed rule groups to `infrastructure/modules/static-website/variables.tf`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create WAF resources file and IP set that all stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create new `infrastructure/modules/static-website/waf.tf` file with module header comments
- [ ] T006 Add cloudposse/label/null module instance for WAF resources in `infrastructure/modules/static-website/waf.tf`
- [ ] T007 Create `aws_wafv2_ip_set.allowlist` resource with conditional count in `infrastructure/modules/static-website/waf.tf`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - WAF-Protected Website (Priority: P1) 🎯 MVP

**Goal**: Create WAF Web ACL and attach it to CloudFront distribution

**Independent Test**: Run `task tf:plan:dev` and verify WAF Web ACL resource is created and attached to CloudFront distribution

### Implementation for User Story 1

- [ ] T008 [US1] Add cloudposse/waf/aws module v1.17.0 source block in `infrastructure/modules/static-website/waf.tf`
- [ ] T009 [US1] Configure WAF module with `scope = "CLOUDFRONT"` and `default_action = "block"` in `infrastructure/modules/static-website/waf.tf`
- [ ] T010 [US1] Add `ip_set_reference_statement_rules` with IP set reference and `action = "allow"` in `infrastructure/modules/static-website/waf.tf`
- [ ] T011 [US1] Add `web_acl_id` parameter to existing CloudFront module call in `infrastructure/modules/static-website/main.tf`
- [ ] T012 [US1] Add `waf_web_acl_id` and `waf_web_acl_arn` outputs to `infrastructure/modules/static-website/outputs.tf`

**Checkpoint**: WAF Web ACL created and attached to CloudFront. Run `task tf:plan:dev` to verify.

---

## Phase 4: User Story 2 - Whitelisted IP Access (Priority: P1)

**Goal**: Ensure only whitelisted IPs can access the site (deny-by-default)

**Independent Test**: Deploy and verify whitelisted IP gets 200 OK while non-whitelisted IP gets 403 Forbidden

### Implementation for User Story 2

- [ ] T013 [US2] Configure IP set to extract IPs from `waf_whitelisted_ips` variable in `infrastructure/modules/static-website/waf.tf`
- [ ] T014 [US2] Add `visibility_config` for CloudWatch metrics on IP allowlist rule in `infrastructure/modules/static-website/waf.tf`
- [ ] T015 [US2] Add `waf_ip_set_arn` output to `infrastructure/modules/static-website/outputs.tf`
- [ ] T016 [US2] Update `infrastructure/environments/dev/terraform.tfvars.json` with default whitelisted IP

**Checkpoint**: Whitelisted IP (157.157.199.250) can access site, all others blocked. Test with `curl` from different IPs.

---

## Phase 5: User Story 3 - Configurable WAF Settings (Priority: P2)

**Goal**: Allow enabling/disabling WAF and configuring managed rules

**Independent Test**: Set `enable_waf = false` and verify no WAF resources are created

### Implementation for User Story 3

- [ ] T017 [US3] Add conditional `count` to WAF module based on `var.enable_waf` in `infrastructure/modules/static-website/waf.tf`
- [ ] T018 [US3] Add `managed_rule_group_statement_rules` block using `var.waf_managed_rules` in `infrastructure/modules/static-website/waf.tf`
- [ ] T019 [US3] Add rule exclusion support within managed rule groups in `infrastructure/modules/static-website/waf.tf`
- [ ] T020 [US3] Update conditional outputs to handle `enable_waf = false` in `infrastructure/modules/static-website/outputs.tf`

**Checkpoint**: WAF can be disabled via variable. Managed rules can be added optionally.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, documentation, and environment configuration

- [ ] T021 [P] Run `task tf:validate:dev` to verify Terraform syntax
- [ ] T022 [P] Run `task tf:plan:dev` to verify resources are created correctly
- [ ] T023 Add provider alias configuration to environment files in `infrastructure/environments/dev/main.tf` and `infrastructure/environments/prod/main.tf`
- [ ] T024 Update quickstart.md with actual test results in `specs/002-static-website-waf/quickstart.md`
- [ ] T025 Run `task tf:apply:dev` and verify WAF attachment in AWS Console

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 and can proceed in parallel
  - US3 (P2) can also proceed in parallel but lower priority
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Creates WAF and attaches to CloudFront
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Configures IP allowlist behavior
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Adds enable/disable and managed rules

### Within Each User Story

- WAF module configuration before CloudFront integration
- Variables/outputs alongside implementation
- Validate with `terraform plan` before moving to next story

### Parallel Opportunities

- T002, T003, T004 can run in parallel (different variables in same file, no conflicts)
- T021, T022 can run in parallel (different commands)
- US1 and US2 tasks can be interleaved (both P1 priority)

---

## Parallel Example: Setup Phase

```bash
# Launch all variable additions together:
Task: "Add enable_waf variable to infrastructure/modules/static-website/variables.tf"
Task: "Add waf_whitelisted_ips variable to infrastructure/modules/static-website/variables.tf"
Task: "Add waf_managed_rules variable to infrastructure/modules/static-website/variables.tf"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (variables, provider alias)
2. Complete Phase 2: Foundational (waf.tf, IP set)
3. Complete Phase 3: User Story 1 (WAF module, CloudFront attachment)
4. **STOP and VALIDATE**: Run `task tf:plan:dev` - verify WAF attached to CloudFront
5. Deploy with `task tf:apply:dev` if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → `terraform plan` shows WAF attached → MVP!
3. Add User Story 2 → IP allowlist enforced → Test with curl
4. Add User Story 3 → Enable/disable working → Full feature complete
5. Each story adds value without breaking previous stories

### Single Developer Strategy

Since this is a Terraform module (single codebase):

1. Complete Setup phase (T001-T004)
2. Complete Foundational phase (T005-T007)
3. Implement US1 (T008-T012) → validate
4. Implement US2 (T013-T016) → validate
5. Implement US3 (T017-T020) → validate
6. Polish phase (T021-T025) → final validation

---

## Notes

- All tasks modify files in `infrastructure/modules/static-website/`
- WAF resources MUST be created in us-east-1 for CloudFront scope
- Use `count = var.enable_waf ? 1 : 0` pattern for conditional resources
- Validate with `task tf:plan:dev` after each phase
- No unit tests - validation via Terraform plan and manual curl testing
- Avoid: creating resources outside us-east-1, missing conditional counts, breaking existing CloudFront config
