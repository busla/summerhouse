# Implementation Plan: Static Website WAF Protection

**Branch**: `002-static-website-waf` | **Date**: 2025-12-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-static-website-waf/spec.md`

## Summary

Add AWS WAF protection to the static-website Terraform module using cloudposse/waf/aws v1.17.0. The WAF implements a strict IP allowlist (deny-by-default) where ONLY whitelisted IPs can access the site. The default whitelisted IP is 157.157.199.250. All other IPs receive 403 Forbidden. The module exposes variables for additional IPs (as objects with ip/description), managed rule groups, and rule exclusions.

## Technical Context

**Language/Version**: HCL (Terraform >= 1.5.0)
**Primary Dependencies**: cloudposse/waf/aws v1.17.0, cloudposse/label/null ~> 0.25, terraform-aws-modules/cloudfront/aws ~> 6.0
**Storage**: N/A (Infrastructure as Code module)
**Testing**: Terraform validate, terraform plan, manual integration testing
**Target Platform**: AWS (CloudFront + WAF in us-east-1 for CLOUDFRONT scope)
**Project Type**: Terraform module extension
**Performance Goals**: N/A (infrastructure module)
**Constraints**: WAF for CloudFront MUST be scoped to CLOUDFRONT and deployed in us-east-1
**Scale/Scope**: Single module enhancement, ~100-200 lines of Terraform

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Terraform validate/plan serves as test; manual verification via curl |
| II. Simplicity & YAGNI | ✅ PASS | Using existing cloudposse/waf module, not building from scratch |
| III. Type Safety | ✅ PASS | Terraform variables with explicit types and validation |
| IV. Observability | ✅ PASS | WAF outputs ACL ID/ARN; CloudWatch metrics available via visibility_config |
| V. Incremental Delivery | ✅ PASS | WAF can be enabled/disabled via variable; no breaking changes |
| VI. Technology Stack | ✅ PASS | Uses cloudposse modules per CLAUDE.md conventions |

**Infrastructure Note**: This feature does NOT use `terraform-aws-agentcore` as it's a static website WAF, not an agent deployment. Uses terraform-aws-modules/cloudfront (already in use) and cloudposse modules per project conventions.

## Project Structure

### Documentation (this feature)

```text
specs/002-static-website-waf/
├── spec.md              # Feature specification (done)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (Terraform variables/outputs)
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
infrastructure/
└── modules/
    └── static-website/
        ├── main.tf          # Existing - add WAF module call
        ├── variables.tf     # Existing - add WAF variables
        ├── outputs.tf       # Existing - add WAF outputs
        └── waf.tf           # NEW - WAF-specific resources
```

**Structure Decision**: Extend the existing `static-website` module by adding a new `waf.tf` file for WAF-specific resources, plus updating `variables.tf` and `outputs.tf`. This follows the module's existing pattern and keeps WAF concerns isolated while maintaining a cohesive module interface.

## Complexity Tracking

No constitution violations - no entries needed.
