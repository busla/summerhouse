# Static Website Module - WAF Resources
# AWS WAF protection for CloudFront distribution
#
# Architecture:
# - WAF Web ACL with deny-by-default (block all non-whitelisted IPs)
# - Separate IP Sets for IPv4 and IPv6 allowlisted addresses
# - Optional AWS Managed Rule Groups
#
# Note: All WAF resources must be in us-east-1 for CloudFront scope
# Uses provider alias: aws.us_east_1

# -----------------------------------------------------------------------------
# CloudPosse Label for WAF resources
# -----------------------------------------------------------------------------

module "waf_label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  # Inherit from main label, add WAF-specific naming
  context    = module.label.context
  attributes = ["waf"]
}

# -----------------------------------------------------------------------------
# Local variables for IP address family separation
# -----------------------------------------------------------------------------

locals {
  # Split whitelisted IPs into IPv4 and IPv6 lists
  # IPv6 addresses contain colons (:), IPv4 addresses do not
  ipv4_addresses = [
    for entry in var.waf_whitelisted_ips : entry.ip
    if !can(regex(":", entry.ip))
  ]

  ipv6_addresses = [
    for entry in var.waf_whitelisted_ips : entry.ip
    if can(regex(":", entry.ip))
  ]

  # Determine which IP sets to create
  has_ipv4 = length(local.ipv4_addresses) > 0
  has_ipv6 = length(local.ipv6_addresses) > 0

  # Determine if we need OR logic (both IPv4 and IPv6 present)
  needs_or_statement = local.has_ipv4 && local.has_ipv6
}

# -----------------------------------------------------------------------------
# WAF IP Sets for Allowlisted IPs (separate sets for IPv4 and IPv6)
# -----------------------------------------------------------------------------

resource "aws_wafv2_ip_set" "allowlist_ipv4" {
  count = var.enable_waf && local.has_ipv4 ? 1 : 0

  provider           = aws.us_east_1
  name               = "${module.waf_label.id}-allowlist-ipv4"
  scope              = "CLOUDFRONT"
  ip_address_version = "IPV4"
  addresses          = local.ipv4_addresses

  tags = module.waf_label.tags
}

resource "aws_wafv2_ip_set" "allowlist_ipv6" {
  count = var.enable_waf && local.has_ipv6 ? 1 : 0

  provider           = aws.us_east_1
  name               = "${module.waf_label.id}-allowlist-ipv6"
  scope              = "CLOUDFRONT"
  ip_address_version = "IPV6"
  addresses          = local.ipv6_addresses

  tags = module.waf_label.tags
}

# -----------------------------------------------------------------------------
# WAF Web ACL (using cloudposse/waf/aws)
# -----------------------------------------------------------------------------

module "waf" {
  count = var.enable_waf ? 1 : 0

  source  = "cloudposse/waf/aws"
  version = "1.17.0"

  providers = {
    aws = aws.us_east_1
  }

  # Inherit naming from WAF label
  context = module.waf_label.context

  # CloudFront scope (must be in us-east-1)
  scope = "CLOUDFRONT"

  # Deny-by-default: block all requests that don't match allow rules
  default_action = "block"

  # IP allowlist rules - separate rules for IPv4 and IPv6
  # Both use "allow" action so matching either allows the request
  ip_set_reference_statement_rules = concat(
    # IPv4 allowlist rule (priority 1) - only if IPv4 addresses exist
    local.has_ipv4 ? [
      {
        name     = "allow-whitelisted-ipv4"
        action   = "allow"
        priority = 1

        statement = {
          arn = aws_wafv2_ip_set.allowlist_ipv4[0].arn
        }

        visibility_config = {
          cloudwatch_metrics_enabled = true
          sampled_requests_enabled   = true
          metric_name                = "${module.waf_label.id}-allowlist-ipv4"
        }
      }
    ] : [],

    # IPv6 allowlist rule (priority 2) - only if IPv6 addresses exist
    local.has_ipv6 ? [
      {
        name     = "allow-whitelisted-ipv6"
        action   = "allow"
        priority = 2

        statement = {
          arn = aws_wafv2_ip_set.allowlist_ipv6[0].arn
        }

        visibility_config = {
          cloudwatch_metrics_enabled = true
          sampled_requests_enabled   = true
          metric_name                = "${module.waf_label.id}-allowlist-ipv6"
        }
      }
    ] : []
  )

  # Optional managed rule groups (evaluated after IP allowlist)
  managed_rule_group_statement_rules = [
    for idx, rule in var.waf_managed_rules : {
      name            = rule.name
      priority        = rule.priority
      override_action = "none"

      statement = {
        name        = rule.name
        vendor_name = rule.vendor_name

        # Rule exclusions if specified
        rule_action_override = [
          for excluded_rule in rule.excluded_rules : {
            name          = excluded_rule
            action_to_use = { count = {} }
          }
        ]
      }

      visibility_config = {
        cloudwatch_metrics_enabled = true
        sampled_requests_enabled   = true
        metric_name                = "${module.waf_label.id}-${rule.name}"
      }
    }
  ]

  # Default visibility config for the Web ACL itself
  visibility_config = {
    cloudwatch_metrics_enabled = true
    sampled_requests_enabled   = true
    metric_name                = module.waf_label.id
  }
}
