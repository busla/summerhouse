# Research: Static Website WAF Protection

**Feature**: 002-static-website-waf
**Date**: 2025-12-29

## Research Topics

### 1. cloudposse/waf/aws Module Integration

**Decision**: Use cloudposse/waf/aws v1.17.0 with `ip_set_reference_statement_rules` for IP allowlisting

**Rationale**:
- Module already provides comprehensive WAF functionality
- Supports IP sets with allow/block actions
- Has `default_action = "block"` which aligns with deny-by-default requirement
- Integrates with cloudposse/label/null context pattern already used in project
- Module creates IP sets internally via `aws_wafv2_ip_set.default`

**Alternatives Considered**:
- Raw `aws_wafv2_web_acl` resource: Rejected - more code, less maintainable
- terraform-aws-modules/waf: Does not exist
- Custom WAF module: Rejected - violates YAGNI principle

### 2. CloudFront WAF Scope Configuration

**Decision**: Configure WAF with `scope = "CLOUDFRONT"` and deploy in us-east-1

**Rationale**:
- AWS WAF for CloudFront distributions MUST be scoped to CLOUDFRONT
- CLOUDFRONT-scoped WAF resources MUST be created in us-east-1 region
- The static-website module already handles CloudFront configuration
- WAF WebACL attaches to CloudFront via `web_acl_id` attribute on distribution

**Alternatives Considered**:
- REGIONAL scope: Invalid for CloudFront distributions
- Deploy in same region as other resources: Would fail - CloudFront requires us-east-1

**Implementation Note**: Requires an AWS provider alias for us-east-1:
```hcl
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
```

### 3. IP Allowlist Architecture

**Decision**: Create IP Set with allowlisted IPs, then use `ip_set_reference_statement_rules` with `action = "allow"` and `default_action = "block"`

**Rationale**:
- `default_action = "block"` ensures deny-by-default behavior
- IP set rule with `action = "allow"` permits only whitelisted IPs
- Supports both IPv4 and IPv6 addresses in CIDR notation
- WAF evaluates rules by priority; allowlist checked before block

**Implementation Pattern**:
```hcl
ip_set_reference_statement_rules = [
  {
    name     = "allow-whitelisted-ips"
    action   = "allow"
    priority = 1  # Evaluated first

    statement = {
      ip_set = {
        ip_set_arn = aws_wafv2_ip_set.allowlist.arn
      }
    }

    visibility_config = {
      cloudwatch_metrics_enabled = true
      sampled_requests_enabled   = true
      metric_name                = "AllowlistedIPs"
    }
  }
]
```

**Alternatives Considered**:
- Geo-blocking with IP exceptions: More complex, same result
- Rate limiting with IP bypass: Doesn't achieve deny-by-default

### 4. Variable Structure for Whitelisted IPs

**Decision**: Use `list(object({ ip = string, description = string }))` for self-documenting IP entries

**Rationale**:
- Description field provides inline documentation for each IP
- Improves auditability - can see why each IP is whitelisted
- Description not used in module logic, only for code clarity
- Terraform validation can enforce CIDR format on `ip` field

**Variable Definition**:
```hcl
variable "waf_whitelisted_ips" {
  description = "List of IP addresses to whitelist. Each entry requires IP in CIDR notation and a description."
  type = list(object({
    ip          = string
    description = string
  }))
  default = [
    {
      ip          = "157.157.199.250/32"
      description = "Primary trusted access IP"
    }
  ]
}
```

**Alternatives Considered**:
- Simple `list(string)`: Rejected - lacks documentation clarity
- Map of description to IP: Less intuitive, harder to iterate

### 5. Managed Rules Configuration

**Decision**: Expose variables for optional managed rule groups with rule exclusions

**Rationale**:
- AWS Managed Rules provide protection against common attack patterns
- Not enabled by default (IP allowlist is primary protection)
- Rule exclusions allow disabling specific rules that cause false positives
- Configuration via variables enables environment-specific tuning

**Variable Structure**:
```hcl
variable "waf_managed_rules" {
  description = "List of AWS Managed Rule Groups to include"
  type = list(object({
    name            = string
    vendor_name     = string
    priority        = number
    excluded_rules  = list(string)
  }))
  default = []
}
```

**Common Managed Rule Groups**:
- `AWSManagedRulesCommonRuleSet` - General protection
- `AWSManagedRulesKnownBadInputsRuleSet` - Known bad input patterns
- `AWSManagedRulesSQLiRuleSet` - SQL injection protection
- `AWSManagedRulesLinuxRuleSet` - Linux-specific attacks

### 6. CloudFront Integration

**Decision**: Pass WAF Web ACL ARN to terraform-aws-modules/cloudfront via `web_acl_id` parameter

**Rationale**:
- The cloudfront module supports `web_acl_id` parameter
- This is the standard method for attaching WAF to CloudFront
- Conditional attachment based on `enable_waf` variable
- No changes needed to existing cloudfront module call structure

**Implementation**:
```hcl
module "cloudfront" {
  source  = "terraform-aws-modules/cloudfront/aws"
  version = "~> 6.0"

  # ... existing configuration ...

  # WAF integration
  web_acl_id = var.enable_waf ? module.waf[0].arn : null
}
```

**Alternatives Considered**:
- aws_wafv2_web_acl_association: For ALB/API Gateway, not CloudFront
- Custom resource: Unnecessary when cloudfront module supports it

## Key Findings Summary

| Topic | Decision | Impact |
|-------|----------|--------|
| WAF Module | cloudposse/waf/aws v1.17.0 | Proven module, follows project patterns |
| WAF Scope | CLOUDFRONT in us-east-1 | Requires provider alias |
| IP Allowlist | IP Set + allow rule + default block | Clean deny-by-default |
| Variable Format | list(object({ip, description})) | Self-documenting IPs |
| Managed Rules | Optional via variable | Flexible protection |
| CloudFront Attach | web_acl_id parameter | Native integration |

## Open Questions Resolved

All technical questions resolved. Ready for Phase 1 design.
