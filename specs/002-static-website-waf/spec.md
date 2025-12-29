# Feature Specification: Static Website WAF Protection

**Feature Branch**: `002-static-website-waf`
**Created**: 2025-12-29
**Status**: Draft
**Input**: User description: "Add the cloudposse/waf/aws version 1.17.0 to the infrastructure/modules/static-websites and whitelist 157.157.199.250"

## Clarifications

### Session 2025-12-29

- Q: WAF access model - should non-whitelisted IPs be blocked or just subject to rules? → A: Strict deny-all: Block ALL non-whitelisted IPs (403 response)
- Q: Should developers be able to configure AWS Managed Rules? → A: Yes, developers can selectively add and exclude managed rules via variables
- Q: How should additional IPs be whitelisted? → A: Via an array of objects variable with `ip` and `description` fields; description is for documentation clarity only (not used in module logic)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Infrastructure Admin Deploys WAF-Protected Website (Priority: P1)

As an infrastructure administrator, I want the static website CloudFront distribution to be protected by AWS WAF so that malicious traffic is blocked before reaching the application.

**Why this priority**: WAF protection is the core requirement of this feature. Without it, the website remains vulnerable to common web attacks like SQL injection, XSS, and bot attacks.

**Independent Test**: Can be fully tested by deploying the infrastructure and verifying that WAF rules are attached to the CloudFront distribution, providing immediate security protection.

**Acceptance Scenarios**:

1. **Given** the static-website module is deployed, **When** Terraform apply completes successfully, **Then** a WAF Web ACL is created and associated with the CloudFront distribution
2. **Given** the WAF is configured, **When** AWS Console is checked, **Then** the Web ACL shows as attached to the CloudFront distribution
3. **Given** the infrastructure is deployed, **When** traffic flows through CloudFront, **Then** AWS WAF evaluates all requests against configured rules

---

### User Story 2 - Whitelisted IP Access (Priority: P1)

As a system owner, I want ONLY specific whitelisted IP addresses (157.157.199.250) to be able to access the website, with ALL other IPs blocked (deny-by-default).

**Why this priority**: Strict IP allowlisting is explicitly required. The site should only be accessible from trusted sources. All non-whitelisted IPs must receive a 403 Forbidden response.

**Independent Test**: Can be tested by making requests from the whitelisted IP (should succeed) and from any non-whitelisted IP (should receive 403 Forbidden).

**Acceptance Scenarios**:

1. **Given** the WAF is deployed with IP whitelist rules, **When** a request comes from 157.157.199.250, **Then** the request is allowed through to CloudFront
2. **Given** the WAF is deployed, **When** a request comes from ANY non-whitelisted IP, **Then** the request is blocked with a 403 Forbidden response
3. **Given** the WAF is deployed, **When** Terraform outputs are examined, **Then** the whitelisted IP (157.157.199.250) is visible in the WAF configuration

---

### User Story 3 - Configurable WAF Settings (Priority: P2)

As an infrastructure administrator, I want WAF settings to be configurable via Terraform variables so that different environments can have different protection levels.

**Why this priority**: While default protection is valuable, allowing configuration enables fine-tuning for dev vs. prod environments and future security adjustments without code changes.

**Independent Test**: Can be tested by deploying with different variable values and verifying the resulting WAF configuration matches the inputs.

**Acceptance Scenarios**:

1. **Given** the module has WAF variables, **When** `enable_waf` is set to false, **Then** no WAF resources are created
2. **Given** the module has WAF variables, **When** additional IPs are provided to the whitelist variable, **Then** those IPs are added to the WAF IP set
3. **Given** the module has WAF variables, **When** custom rate limits are specified, **Then** the WAF rate-based rule uses those limits
4. **Given** the module has managed rules variables, **When** a managed rule group is specified, **Then** that rule group is added to the WAF Web ACL
5. **Given** the module has rule exclusion variables, **When** specific rules are excluded, **Then** those rules are disabled within the managed group

---

### Edge Cases

- What happens when WAF is enabled but no whitelisted IPs are provided? (Default IP 157.157.199.250 still allows access; if removed, ALL traffic is blocked)
- How does the system handle IPv6 addresses in the whitelist? (Should support both IPv4 and IPv6 formats)
- What happens if the WAF module version is unavailable? (Terraform should fail with clear error)
- What response do blocked IPs receive? (403 Forbidden with standard WAF block response)
- What happens if the whitelisted IP list is accidentally emptied? (Site becomes completely inaccessible until IPs are added back)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Module MUST integrate cloudposse/waf/aws version 1.17.0 as a dependency
- **FR-002**: Module MUST create an AWS WAF Web ACL that attaches to the CloudFront distribution
- **FR-003**: Module MUST implement a strict IP allowlist (deny-by-default) - ONLY whitelisted IPs can access the site
- **FR-004**: Module MUST whitelist IP address 157.157.199.250 by default
- **FR-011**: Module MUST block ALL non-whitelisted IPs with a 403 Forbidden response
- **FR-005**: Module MUST expose a variable to enable/disable WAF protection
- **FR-006**: Module MUST expose an array of objects variable for whitelisted IPs with structure `{ip: string, description: string}` (IPv4 and IPv6 supported); description field is for documentation clarity only and not used in module logic
- **FR-007**: WAF Web ACL MUST be scoped to CLOUDFRONT (regional: us-east-1 for global CloudFront)
- **FR-008**: Module MUST use cloudposse/label/null for consistent naming of WAF resources
- **FR-009**: Module MUST output the WAF Web ACL ID and ARN for reference
- **FR-010**: Module MUST preserve existing CloudFront functionality when WAF is added
- **FR-012**: Module MUST expose a variable to selectively include AWS Managed Rule Groups (e.g., AWSManagedRulesCommonRuleSet)
- **FR-013**: Module MUST expose a variable to exclude specific rules within managed rule groups (rule exclusions)

### Key Entities

- **WAF Web ACL**: The main WAF configuration that attaches to CloudFront, contains rules and rule groups
- **IP Set**: Collection of whitelisted IP addresses (from objects with `ip` and `description` fields) that receive special treatment in WAF rules
- **WAF Rules**: Individual security rules (rate limiting, IP whitelist, managed rule groups)
- **Managed Rule Groups**: AWS-provided rule sets (e.g., AWSManagedRulesCommonRuleSet) that can be selectively included
- **Rule Exclusions**: Specific rules within a managed group that are disabled to prevent false positives
- **CloudFront Distribution**: Existing resource that receives WAF protection

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Infrastructure deployment completes successfully with WAF resources provisioned
- **SC-002**: Whitelisted IP (157.157.199.250) can access the website without restrictions
- **SC-003**: Non-whitelisted IPs receive 403 Forbidden when attempting to access the site
- **SC-004**: WAF appears as attached to CloudFront in AWS Console
- **SC-005**: No disruption to existing website functionality for whitelisted IPs after WAF integration
- **SC-006**: Terraform plan shows no unexpected changes to existing resources when adding WAF
- **SC-007**: WAF can be disabled via variable without affecting other module functionality

## Assumptions

- The cloudposse/waf/aws module version 1.17.0 is compatible with the current Terraform version (>= 1.5.0) and AWS provider (>= 5.0)
- WAF operates in strict deny-by-default mode: only whitelisted IPs can access the site
- AWS Managed Rules are configurable: developers can selectively add rule groups and exclude specific rules
- No managed rules are enabled by default (IP allowlist is the primary protection)
- The specified IP 157.157.199.250 is a trusted source requiring permanent whitelist access
- WAF is enabled by default when the variable is not explicitly set
- This is a private/restricted site - public access is not required

## Dependencies

- Existing static-website module with CloudFront distribution
- AWS provider configured with appropriate permissions for WAF
- cloudposse/waf/aws version 1.17.0 from Terraform Registry
