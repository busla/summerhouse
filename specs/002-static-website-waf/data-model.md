# Data Model: Static Website WAF Protection

**Feature**: 002-static-website-waf
**Date**: 2025-12-29
**Type**: Terraform Module Extension (Infrastructure as Code)

## Overview

This document defines the Terraform variables, outputs, and resource structures for adding AWS WAF protection to the static-website module. Unlike application features, this is purely infrastructure configuration with no database tables.

## Resource Relationship Diagram

```
┌─────────────────────┐
│  Static Website     │
│  Module             │
└─────────┬───────────┘
          │ web_acl_id
          ▼
┌─────────────────────┐       ┌─────────────────┐
│  CloudFront         │◀──────│  WAF Web ACL    │
│  Distribution       │       │  (CLOUDFRONT)   │
└─────────────────────┘       └────────┬────────┘
                                       │ references
                                       ▼
                              ┌─────────────────┐
                              │  WAF IP Set     │
                              │  (IPv4/IPv6)    │
                              └─────────────────┘

Region: us-east-1 (required for CloudFront-scoped WAF)
```

## Terraform Variables

### 1. WAF Enable/Disable

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `enable_waf` | bool | `true` | Enable WAF protection for CloudFront distribution |

```hcl
variable "enable_waf" {
  description = "Enable WAF protection for CloudFront distribution"
  type        = bool
  default     = true
}
```

---

### 2. Whitelisted IPs

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `waf_whitelisted_ips` | list(object) | See below | List of IP addresses to whitelist with descriptions |

**Object Structure**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ip` | string | Yes | IP address in CIDR notation (IPv4 or IPv6) |
| `description` | string | Yes | Documentation-only description of the IP |

```hcl
variable "waf_whitelisted_ips" {
  description = "List of IP addresses to whitelist. Each entry requires IP in CIDR notation and a description for documentation clarity."
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

  validation {
    condition = alltrue([
      for entry in var.waf_whitelisted_ips :
      can(cidrhost(entry.ip, 0))
    ])
    error_message = "All IP addresses must be in valid CIDR notation (e.g., 192.168.1.1/32 or 2001:db8::/32)."
  }
}
```

**Usage Example**:
```hcl
waf_whitelisted_ips = [
  {
    ip          = "157.157.199.250/32"
    description = "Primary trusted access IP"
  },
  {
    ip          = "203.0.113.0/24"
    description = "Office network CIDR"
  },
  {
    ip          = "2001:db8::1/128"
    description = "IPv6 developer workstation"
  }
]
```

---

### 3. Managed Rule Groups (Optional)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `waf_managed_rules` | list(object) | `[]` | Optional AWS Managed Rule Groups to include |

**Object Structure**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Managed rule group name (e.g., `AWSManagedRulesCommonRuleSet`) |
| `vendor_name` | string | Yes | Vendor name (typically `AWS`) |
| `priority` | number | Yes | Rule priority (lower = evaluated first) |
| `excluded_rules` | list(string) | No | List of rule names to exclude from this group |

```hcl
variable "waf_managed_rules" {
  description = "List of AWS Managed Rule Groups to include. Empty by default (IP allowlist is primary protection)."
  type = list(object({
    name           = string
    vendor_name    = string
    priority       = number
    excluded_rules = optional(list(string), [])
  }))
  default = []
}
```

**Usage Example**:
```hcl
waf_managed_rules = [
  {
    name           = "AWSManagedRulesCommonRuleSet"
    vendor_name    = "AWS"
    priority       = 10
    excluded_rules = ["SizeRestrictions_BODY"]
  },
  {
    name           = "AWSManagedRulesKnownBadInputsRuleSet"
    vendor_name    = "AWS"
    priority       = 20
    excluded_rules = []
  }
]
```

**Common AWS Managed Rule Groups**:

| Rule Group Name | Description | Use Case |
|-----------------|-------------|----------|
| `AWSManagedRulesCommonRuleSet` | OWASP Top 10 protection | General web security |
| `AWSManagedRulesKnownBadInputsRuleSet` | Known bad input patterns | Input validation |
| `AWSManagedRulesSQLiRuleSet` | SQL injection protection | Database security |
| `AWSManagedRulesLinuxRuleSet` | Linux-specific attacks | OS protection |
| `AWSManagedRulesAmazonIpReputationList` | IP reputation | Bot protection |

---

## Terraform Outputs

### 1. WAF Web ACL Outputs

| Output | Type | Description |
|--------|------|-------------|
| `waf_web_acl_id` | string | WAF Web ACL ID (null if WAF disabled) |
| `waf_web_acl_arn` | string | WAF Web ACL ARN (null if WAF disabled) |
| `waf_ip_set_arn` | string | WAF IP Set ARN containing whitelisted IPs |

```hcl
output "waf_web_acl_id" {
  description = "WAF Web ACL ID (null if WAF disabled)"
  value       = var.enable_waf ? module.waf[0].id : null
}

output "waf_web_acl_arn" {
  description = "WAF Web ACL ARN (null if WAF disabled)"
  value       = var.enable_waf ? module.waf[0].arn : null
}

output "waf_ip_set_arn" {
  description = "WAF IP Set ARN containing whitelisted IPs"
  value       = var.enable_waf ? aws_wafv2_ip_set.allowlist[0].arn : null
}
```

---

## AWS Resources Created

### 1. WAF IP Set

**Resource**: `aws_wafv2_ip_set.allowlist`

| Attribute | Value | Description |
|-----------|-------|-------------|
| `name` | `{label.id}-allowlist` | Resource name from cloudposse/label |
| `scope` | `CLOUDFRONT` | Required for CloudFront distributions |
| `ip_address_version` | `IPV4` | IPv4 addresses (separate set for IPv6 if needed) |
| `addresses` | From variable | List of CIDR blocks from `waf_whitelisted_ips` |

```hcl
resource "aws_wafv2_ip_set" "allowlist" {
  count = var.enable_waf ? 1 : 0

  provider           = aws.us_east_1
  name               = "${module.label.id}-allowlist"
  scope              = "CLOUDFRONT"
  ip_address_version = "IPV4"
  addresses          = [for entry in var.waf_whitelisted_ips : entry.ip]

  tags = module.label.tags
}
```

### 2. WAF Web ACL (via cloudposse/waf/aws)

**Module**: `cloudposse/waf/aws` v1.17.0

| Parameter | Value | Description |
|-----------|-------|-------------|
| `scope` | `CLOUDFRONT` | Required for CloudFront |
| `default_action` | `block` | Deny-by-default behavior |
| `ip_set_reference_statement_rules` | Allow rule | References IP set with allow action |
| `managed_rule_group_statement_rules` | From variable | Optional managed rules |

**Rule Priority Order**:
1. **Priority 1**: IP allowlist rule (action: allow)
2. **Priority 10+**: Managed rule groups (if configured)
3. **Default action**: Block all non-matching requests

---

## Configuration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     WAF Request Evaluation                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Incoming Request                                                │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────┐                            │
│  │ Rule 1: IP Allowlist (Priority 1)│                           │
│  │ Action: ALLOW                    │                           │
│  └───────────────┬─────────────────┘                            │
│                  │                                               │
│        ┌─────────┴─────────┐                                    │
│        │ IP Whitelisted?   │                                    │
│        └─────────┬─────────┘                                    │
│           Yes    │    No                                         │
│            ▼     │     ▼                                         │
│      ┌───────┐   │  ┌─────────────────────────────┐             │
│      │ ALLOW │   │  │ Rules 10+: Managed Rules    │             │
│      └───────┘   │  │ (if configured)             │             │
│                  │  └─────────────┬───────────────┘             │
│                  │                │                              │
│                  │       ┌────────┴────────┐                    │
│                  │       │ Rule matched?   │                    │
│                  │       └────────┬────────┘                    │
│                  │         Yes    │    No                        │
│                  │          ▼     │     ▼                        │
│                  │    ┌───────┐   │  ┌───────────────┐          │
│                  │    │ BLOCK │   │  │ Default Action│          │
│                  │    └───────┘   │  │    (BLOCK)    │          │
│                  │                │  └───────────────┘          │
│                  │                │          │                   │
│                  │                │          ▼                   │
│                  │                │    ┌───────────┐             │
│                  │                │    │ 403       │             │
│                  │                │    │ Forbidden │             │
│                  │                │    └───────────┘             │
│                  │                │                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Provider Configuration

WAF for CloudFront must be created in us-east-1. The module requires an AWS provider alias:

```hcl
# In environments/dev/main.tf or environments/prod/main.tf
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

module "static_website" {
  source = "../../modules/static-website"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  # ... other variables
}
```

---

## Validation Rules

### IP Address Format

```hcl
validation {
  condition = alltrue([
    for entry in var.waf_whitelisted_ips :
    can(cidrhost(entry.ip, 0))
  ])
  error_message = "All IP addresses must be in valid CIDR notation."
}
```

### Description Required

The variable type enforces that every IP must have a description. Empty descriptions are allowed but discouraged.

---

## Sample Configurations

### Minimal (Default)

```hcl
module "static_website" {
  source = "../../modules/static-website"

  # WAF enabled by default with single IP
  # waf_whitelisted_ips uses default: 157.157.199.250/32
}
```

### Multiple IPs

```hcl
module "static_website" {
  source = "../../modules/static-website"

  waf_whitelisted_ips = [
    {
      ip          = "157.157.199.250/32"
      description = "Primary trusted access IP"
    },
    {
      ip          = "10.0.0.0/8"
      description = "Internal network"
    },
    {
      ip          = "192.168.1.100/32"
      description = "Developer home office"
    }
  ]
}
```

### With Managed Rules

```hcl
module "static_website" {
  source = "../../modules/static-website"

  waf_whitelisted_ips = [
    {
      ip          = "157.157.199.250/32"
      description = "Primary trusted access IP"
    }
  ]

  waf_managed_rules = [
    {
      name           = "AWSManagedRulesCommonRuleSet"
      vendor_name    = "AWS"
      priority       = 10
      excluded_rules = []
    }
  ]
}
```

### WAF Disabled

```hcl
module "static_website" {
  source = "../../modules/static-website"

  enable_waf = false
}
```
